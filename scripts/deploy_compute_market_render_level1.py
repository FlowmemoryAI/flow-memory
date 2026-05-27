from __future__ import annotations

import argparse
import base64
import ipaddress
import json
import hmac
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
SERVICE_NAME = os.environ.get("RENDER_SERVICE_NAME", "flow-memory-compute-market-api")
POSTGRES_NAME = "flow-memory-compute-market-postgres"
KEYVALUE_NAME = "flow-memory-compute-market-redis"
DEFAULT_AUDIT_EXPORT_URI = os.environ.get("FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_URI", "")
DEFAULT_LOCAL_AUDIT_EXPORT_URI = "/var/lib/flow-memory/audit/compute-market.ndjson"
DEFAULT_POSTGRES_PLAN = os.environ.get("RENDER_POSTGRES_PLAN", "basic_256mb")
DEFAULT_KEYVALUE_PLAN = os.environ.get("RENDER_KEYVALUE_PLAN", "starter")
DEFAULT_SERVICE_PLAN = os.environ.get("RENDER_SERVICE_PLAN", "starter")
DEFAULT_KEYVALUE_IP_ALLOWLIST = os.environ.get("RENDER_KEYVALUE_IP_ALLOWLIST", "0.0.0.0/32").strip()
ALLOW_FREE_RENDER_PLANS = os.environ.get("RENDER_ALLOW_FREE_PLANS", "").strip().lower() in {"1", "true", "yes"}
ENABLE_RENDER_DISK = os.environ.get("RENDER_ENABLE_DISK", "").strip().lower() in {"1", "true", "yes"}
FREE_RENDER_PLANS = {"free"}
RENDER_AUDIT_DISK_NAME = "compute-market-audit"
RENDER_AUDIT_DISK_MOUNT_PATH = "/var/lib/flow-memory/audit"
RENDER_AUDIT_DISK_SIZE_GB = 10

DEFAULT_AUDIT_EXPORT_OBJECT_LOCK_MODE = os.environ.get(
    "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_OBJECT_LOCK_MODE", ""
)
DEFAULT_AUDIT_EXPORT_RETENTION_DAYS = os.environ.get("FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_RETENTION_DAYS", "0")
DEFAULT_AUDIT_EXPORT_IMMUTABLE_REQUIRED = os.environ.get(
    "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_IMMUTABLE_REQUIRED", "false"
)
DEFAULT_AUDIT_EXPORT_S3_REGION = os.environ.get("FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_S3_REGION", "")
DEFAULT_AUDIT_EXPORT_S3_ENDPOINT_URL = os.environ.get("FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_S3_ENDPOINT_URL", "")
DEFAULT_STRIPE_WEBHOOK_TOLERANCE_SECONDS = os.environ.get("FLOW_MEMORY_BILLING_STRIPE_WEBHOOK_TOLERANCE_SECONDS", "300")
LEVEL1_EXPECTED_BOOLEAN_SETTINGS = {
    "FLOW_MEMORY_COMPUTE_REQUIRE_MANAGED_SQL_IN_PRODUCTION": "true",
    "FLOW_MEMORY_COMPUTE_REQUIRE_MANAGED_REDIS_IN_PRODUCTION": "true",
    "FLOW_MEMORY_API_ENABLE_NONCE_CHECK": "true",
    "FLOW_MEMORY_API_NONCE_FAIL_CLOSED": "true",
    "FLOW_MEMORY_API_NONCE_REQUIRE_TLS": "true",
    "FLOW_MEMORY_COMPUTE_DRY_RUN_REQUIRED": "true",
    "FLOW_MEMORY_COMPUTE_LIVE_SETTLEMENT_ENABLED": "false",
    "FLOW_MEMORY_COMPUTE_BROADCAST_ENABLED": "false",
    "FLOW_MEMORY_COMPUTE_PRIVATE_KEY_INPUTS_ALLOWED": "false",
    "FLOW_MEMORY_COMPUTE_AUDIT_REQUIRED": "true",
    "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_REQUIRED": "true",
    "FLOW_MEMORY_COMPUTE_RATE_LIMITS_ENABLED": "true",
    "FLOW_MEMORY_COMPUTE_CIRCUIT_BREAKER_ENABLED": "true",
    "FLOW_MEMORY_COMPUTE_METRICS_ENABLED": "true",
    "FLOW_MEMORY_COMPUTE_TRACING_ENABLED": "true",
    "FLOW_MEMORY_BILLING_STRIPE_CHECKOUT_ENABLED": "false",
}
DEFAULT_PROVIDER_CALLBACK_IP_ALLOWLIST = os.environ.get("FLOW_MEMORY_COMPUTE_PROVIDER_CALLBACK_IP_ALLOWLIST", "").strip()
DEFAULT_API_JWT_HS256_SECRET = os.environ.get("FLOW_MEMORY_API_JWT_HS256_SECRET", "").strip()
DEFAULT_API_JWT_ISSUER = os.environ.get("FLOW_MEMORY_API_JWT_ISSUER", "").strip()
DEFAULT_API_JWT_AUDIENCE = os.environ.get("FLOW_MEMORY_API_JWT_AUDIENCE", "").strip()
DEFAULT_API_JWT_LEEWAY_SECONDS = os.environ.get("FLOW_MEMORY_API_JWT_LEEWAY_SECONDS", "").strip()
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
    "src/flow_memory/compute_market/models.py",
    "src/flow_memory/compute_market/observability.py",
    "src/flow_memory/compute_market/provider_contracts.py",
    "src/flow_memory/compute_market/planner.py",
    "src/flow_memory/compute_market/pricing.py",
    "src/flow_memory/compute_market/provider_sandbox.py",
    "src/flow_memory/compute_market/registry.py",
    "src/flow_memory/compute_market/service.py",
    "src/flow_memory/compute_market/storage.py",
    "src/flow_memory/compute_market/storage_backends.py",
    "src/flow_memory/compute_market/__init__.py",
    "scripts/deploy_compute_market_public_level1.ps1",
    "scripts/deploy_compute_market_render_level1.py",
    "scripts/smoke_compute_market_public.ps1",
    "scripts/validate_compute_market_public_buildout.py",
    "deployments/compute-market/grafana-dashboard.json",
    "deployments/compute-market/prometheus-alerts.yml",
)
PLACEHOLDERS = (
    "CHANGEME",
    "<required>",
    "<your-domain>",
    "yourdomain.com",
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
    uri = DEFAULT_AUDIT_EXPORT_URI or values.get("FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_URI", "")
    if not uri or has_placeholder(uri):
        return DEFAULT_LOCAL_AUDIT_EXPORT_URI
    return uri


def audit_export_s3_region_from_env(values: dict[str, str], audit_export_uri: str) -> str:
    if not audit_export_uri.startswith("s3://"):
        return ""
    region = DEFAULT_AUDIT_EXPORT_S3_REGION or values.get("FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_S3_REGION", "")
    if not region or has_placeholder(region):
        emit(
            "blocked_missing_audit_object_storage",
            23,
            missing_values=["FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_S3_REGION"],
            required_action="configure FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_S3_REGION for the S3 Object Lock audit export bucket",
        )
    return region


def _audit_export_setting(values: dict[str, str], key: str, default: str) -> str:
    return values.get(key) or default


def _env_setting(values: dict[str, str], key: str, default: str = "") -> str:
    return values.get(key) or default


def _truthy_env(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _bool_setting(values: dict[str, str], key: str, default: bool) -> bool:
    raw = values.get(key, "")
    if not raw:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}




def normalized_bool_text(value: str) -> str:
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return "true"
    if lowered in {"0", "false", "no", "off"}:
        return "false"
    return lowered


def assert_level1_safety_settings(values: dict[str, str]) -> None:
    invalid = [
        {"key": key, "expected": expected, "actual": values[key]}
        for key, expected in LEVEL1_EXPECTED_BOOLEAN_SETTINGS.items()
        if key in values and values[key].strip() and normalized_bool_text(values[key]) != expected
    ]
    if invalid:
        emit(
            "blocked_unsafe_level1_config",
            38,
            invalid_values=invalid,
            required_action="Level 1 Render deployment is planning-only: keep dry-run, audit, immutable export, managed backend, and no-custody billing safety settings intact.",
        )


def assert_https_observability_sink_url(url: str, key: str) -> None:
    if url and url_scheme(url) != "https":
        emit(
            "blocked_insecure_observability_sink",
            29,
            invalid_value=key,
            url_scheme=url_scheme(url),
            required_scheme="https",
            required_action=f"{key} must be an https:// public observability sink URL",
        )


def observability_sink_url_from_env(values: dict[str, str], url_key: str, enabled_key: str) -> str:
    url = values.get(url_key, "").strip()
    enabled = _truthy_env(values.get(enabled_key, ""))
    if enabled and not url:
        emit(
            "blocked_missing_observability_sink",
            29,
            missing_values=[url_key],
            required_action=f"configure {url_key} or disable {enabled_key} before public deployment",
        )
    assert_https_observability_sink_url(url, url_key)
    return url


def provider_callback_ip_allowlist_from_env(values: dict[str, str]) -> str:
    allowlist = DEFAULT_PROVIDER_CALLBACK_IP_ALLOWLIST or values.get("FLOW_MEMORY_COMPUTE_PROVIDER_CALLBACK_IP_ALLOWLIST", "")
    allowlist = allowlist.strip()
    external_quotes_enabled = _truthy_env(values.get("FLOW_MEMORY_COMPUTE_EXTERNAL_QUOTES_ENABLED", ""))
    external_execution_enabled = _truthy_env(values.get("FLOW_MEMORY_COMPUTE_EXTERNAL_EXECUTION_ENABLED", ""))

    if (external_quotes_enabled or external_execution_enabled) and not allowlist:
        emit(
            "blocked_missing_provider_callback_allowlist",
            30,
            missing_values=["FLOW_MEMORY_COMPUTE_PROVIDER_CALLBACK_IP_ALLOWLIST"],
            required_action=(
                "configure explicit provider callback source IPs before enabling external provider "
                "quotes or execution"
            ),
        )

    invalid_entries: list[dict[str, str]] = []
    for entry in (item.strip() for item in allowlist.split(",") if item.strip()):
        if has_placeholder(entry):
            invalid_entries.append({"value": entry, "reason": "placeholder_not_allowed"})
            continue
        try:
            if "/" in entry:
                network = ipaddress.ip_network(entry, strict=True)
                if network.prefixlen == 0:
                    invalid_entries.append({"value": entry, "reason": "world_open_cidr_not_allowed"})
            else:
                address = ipaddress.ip_address(entry)
                if address.is_unspecified:
                    invalid_entries.append({"value": entry, "reason": "unspecified_ip_not_allowed"})
        except ValueError as exc:
            invalid_entries.append({"value": entry, "reason": str(exc)})

    if invalid_entries:
        emit(
            "blocked_invalid_provider_callback_allowlist",
            31,
            invalid_values=invalid_entries,
            required_action=(
                "set FLOW_MEMORY_COMPUTE_PROVIDER_CALLBACK_IP_ALLOWLIST to explicit provider IP "
                "addresses or non-world-open CIDR ranges"
            ),
        )
    return allowlist


def validate_gateway_jwt_config(secret: str, issuer: str, audience: str, leeway_seconds: str) -> None:
    configured = any((secret, issuer, audience))
    if not configured:
        return

    missing: list[str] = []
    if not secret or has_placeholder(secret):
        missing.append("FLOW_MEMORY_API_JWT_HS256_SECRET")
    if not issuer or has_placeholder(issuer):
        missing.append("FLOW_MEMORY_API_JWT_ISSUER")
    if not audience or has_placeholder(audience):
        missing.append("FLOW_MEMORY_API_JWT_AUDIENCE")
    if missing:
        emit(
            "blocked_incomplete_gateway_jwt",
            32,
            missing_values=missing,
            required_action=(
                "configure FLOW_MEMORY_API_JWT_HS256_SECRET, FLOW_MEMORY_API_JWT_ISSUER, "
                "and FLOW_MEMORY_API_JWT_AUDIENCE together for public gateway JWT auth"
            ),
        )

    if len(secret) < 32:
        emit(
            "blocked_weak_gateway_jwt_secret",
            32,
            invalid_value="FLOW_MEMORY_API_JWT_HS256_SECRET",
            required_action="use a high-entropy gateway JWT HS256 secret with at least 32 characters",
        )
    if not issuer.startswith("https://"):
        emit(
            "blocked_insecure_gateway_jwt_issuer",
            32,
            invalid_value="FLOW_MEMORY_API_JWT_ISSUER",
            required_scheme="https",
            required_action="use an https:// issuer URL for public gateway JWT auth",
        )
    try:
        leeway = int(leeway_seconds)
    except ValueError:
        emit(
            "blocked_invalid_gateway_jwt_leeway",
            32,
            invalid_value="FLOW_MEMORY_API_JWT_LEEWAY_SECONDS",
            required_action="set FLOW_MEMORY_API_JWT_LEEWAY_SECONDS to a non-negative integer",
        )
        return
    if leeway < 0:
        emit(
            "blocked_invalid_gateway_jwt_leeway",
            32,
            invalid_value="FLOW_MEMORY_API_JWT_LEEWAY_SECONDS",
            required_action="set FLOW_MEMORY_API_JWT_LEEWAY_SECONDS to a non-negative integer",
        )


def gateway_jwt_config_from_env(values: dict[str, str]) -> dict[str, str]:
    secret = DEFAULT_API_JWT_HS256_SECRET or values.get("FLOW_MEMORY_API_JWT_HS256_SECRET", "")
    issuer = DEFAULT_API_JWT_ISSUER or values.get("FLOW_MEMORY_API_JWT_ISSUER", "")
    audience = DEFAULT_API_JWT_AUDIENCE or values.get("FLOW_MEMORY_API_JWT_AUDIENCE", "")
    leeway_seconds = DEFAULT_API_JWT_LEEWAY_SECONDS or values.get("FLOW_MEMORY_API_JWT_LEEWAY_SECONDS", "60")
    secret = secret.strip()
    issuer = issuer.strip()
    audience = audience.strip()
    leeway_seconds = leeway_seconds.strip() or "60"
    validate_gateway_jwt_config(secret, issuer, audience, leeway_seconds)
    return {
        "FLOW_MEMORY_API_JWT_HS256_SECRET": secret,
        "FLOW_MEMORY_API_JWT_ISSUER": issuer,
        "FLOW_MEMORY_API_JWT_AUDIENCE": audience,
        "FLOW_MEMORY_API_JWT_LEEWAY_SECONDS": leeway_seconds,
    }


def has_placeholder(value: str) -> bool:
    return any(token in value for token in PLACEHOLDERS)


def validate_render_plans(
    *,
    postgres_plan: str | None = None,
    keyvalue_plan: str | None = None,
    service_plan: str | None = None,
    allow_free: bool | None = None,
) -> None:
    postgres_plan = DEFAULT_POSTGRES_PLAN if postgres_plan is None else postgres_plan
    keyvalue_plan = DEFAULT_KEYVALUE_PLAN if keyvalue_plan is None else keyvalue_plan
    service_plan = DEFAULT_SERVICE_PLAN if service_plan is None else service_plan
    allow_free = ALLOW_FREE_RENDER_PLANS if allow_free is None else allow_free
    if allow_free:
        return
    free_plans = [
        {"env": env_name, "value": value}
        for env_name, value in (
            ("RENDER_POSTGRES_PLAN", postgres_plan),
            ("RENDER_KEYVALUE_PLAN", keyvalue_plan),
            ("RENDER_SERVICE_PLAN", service_plan),
        )
        if value.strip().lower() == "free"
    ]
    if free_plans:
        emit(
            "blocked_free_render_plan",
            28,
            invalid_values=free_plans,
            required_action=(
                "Set RENDER_POSTGRES_PLAN, RENDER_KEYVALUE_PLAN, and RENDER_SERVICE_PLAN to production-grade "
                "paid plans, or set RENDER_ALLOW_FREE_PLANS=true only for non-production smoke deployments."
            ),
        )


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


def service_env_value(api_key: str, service_id: str, key: str) -> str:
    items = render_request(
        api_key,
        "GET",
        f"/services/{urllib.parse.quote(service_id)}/env-vars?{query({'limit': '100'})}",
    )
    for item in items if isinstance(items, list) else []:
        env_var = item.get("envVar", item) if isinstance(item, dict) else {}
        if isinstance(env_var, dict) and env_var.get("key") == key:
            return str(env_var.get("value", "") or "")
    return ""


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


def _plan_name(resource: dict[str, Any]) -> str:
    return str(resource.get("plan", "") or "").strip().lower()


def _requires_paid_plan_update(resource: dict[str, Any], target_plan: str) -> bool:
    return _plan_name(resource) in FREE_RENDER_PLANS and target_plan.strip().lower() not in FREE_RENDER_PLANS


def _service_disk_details() -> dict[str, object]:
    return {
        "name": RENDER_AUDIT_DISK_NAME,
        "mountPath": RENDER_AUDIT_DISK_MOUNT_PATH,
        "sizeGB": RENDER_AUDIT_DISK_SIZE_GB,
    }


def _disk_payload(service_id: str) -> dict[str, object]:
    payload = _service_disk_details()
    payload["serviceId"] = service_id
    return payload


def ensure_service_disk(api_key: str, service_id: str) -> dict[str, Any] | None:
    disks = render_request(
        api_key,
        "GET",
        f"/disks?{query({'serviceId': service_id, 'limit': '100'})}",
    )
    for item in disks if isinstance(disks, list) else []:
        disk = item.get("disk", item) if isinstance(item, dict) else {}
        if (
            isinstance(disk, dict)
            and disk.get("serviceId") == service_id
            and disk.get("mountPath") == RENDER_AUDIT_DISK_MOUNT_PATH
        ):
            return disk
    created = render_request(api_key, "POST", "/disks", _disk_payload(service_id))
    return created.get("disk", created) if isinstance(created, dict) else None


def ensure_postgres(api_key: str, owner_id: str, region: str, *, plan: str | None = None) -> dict[str, Any]:
    plan = DEFAULT_POSTGRES_PLAN if plan is None else plan
    existing = find_named(api_key, "/postgres", "postgres", owner_id, POSTGRES_NAME)
    if existing is not None:
        if _requires_paid_plan_update(existing, plan):
            return render_request(
                api_key,
                "PATCH",
                f"/postgres/{urllib.parse.quote(str(existing['id']))}",
                {"plan": plan},
            )
        return existing
    body = {
        "name": POSTGRES_NAME,
        "ownerId": owner_id,
        "plan": plan,
        "version": "16",
        "databaseName": "flow_memory",
        "databaseUser": "flow_memory",
        "region": region,
        "ipAllowList": [],
    }
    return render_request(api_key, "POST", "/postgres", body)


def keyvalue_ip_allow_list(value: str | None = None) -> list[dict[str, str]]:
    raw_value = DEFAULT_KEYVALUE_IP_ALLOWLIST if value is None else value
    entries = [entry.strip() for entry in raw_value.split(",") if entry.strip()]
    if not entries:
        emit(
            "blocked_missing_redis_external_allowlist",
            26,
            missing_values=["RENDER_KEYVALUE_IP_ALLOWLIST"],
            required_action=(
                "Set RENDER_KEYVALUE_IP_ALLOWLIST to the CIDR ranges allowed to reach the Render Key Value "
                "external rediss:// endpoint."
            ),
        )

    invalid_entries: list[dict[str, str]] = []
    for entry in entries:
        if "/" not in entry:
            invalid_entries.append({"value": entry, "reason": "cidr_prefix_required"})
            continue
        try:
            network = ipaddress.ip_network(entry, strict=True)
        except ValueError as exc:
            invalid_entries.append({"value": entry, "reason": str(exc)})
            continue
        if network.prefixlen == 0:
            invalid_entries.append({"value": entry, "reason": "world_open_cidr_not_allowed"})

    if invalid_entries:
        emit(
            "blocked_invalid_redis_external_allowlist",
            27,
            invalid_values=invalid_entries,
            required_action="Set RENDER_KEYVALUE_IP_ALLOWLIST to explicit non-world-open CIDR ranges.",
        )

    return [{"cidrBlock": entry, "description": "flow-memory-compute-market-redis-tls"} for entry in entries]


def ensure_keyvalue(
    api_key: str,
    owner_id: str,
    region: str,
    *,
    plan: str | None = None,
    ip_allowlist: str | None = None,
) -> dict[str, Any]:
    plan = DEFAULT_KEYVALUE_PLAN if plan is None else plan
    ip_allow_list = keyvalue_ip_allow_list(ip_allowlist)
    existing = find_named(api_key, "/key-value", "keyValue", owner_id, KEYVALUE_NAME)
    if existing is not None:
        if _requires_paid_plan_update(existing, plan):
            return render_request(
                api_key,
                "PATCH",
                f"/key-value/{urllib.parse.quote(str(existing['id']))}",
                {
                    "plan": plan,
                    "maxmemoryPolicy": "noeviction",
                    "persistenceMode": "journal_snapshot",
                    "ipAllowList": ip_allow_list,
                },
            )
        return existing
    body = {
        "name": KEYVALUE_NAME,
        "ownerId": owner_id,
        "plan": plan,
        "region": region,
        "maxmemoryPolicy": "noeviction",
        "ipAllowList": ip_allow_list,
    }
    if plan != "free":
        body["persistenceMode"] = "journal_snapshot"
    return render_request(api_key, "POST", "/key-value", body)


def env_var(key: str, value: str) -> dict[str, str]:
    return {"key": key, "value": value}


def url_scheme(value: str) -> str:
    return urllib.parse.urlparse(value).scheme.lower()


def public_url_block_reason(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").strip().strip("[]").lower().rstrip(".")
    if not host:
        return "public_url_missing_host"
    if host in {"localhost", "ip6-localhost", "ip6-loopback"} or host.endswith(".local"):
        return "public_url_must_not_use_localhost"
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return ""
    return "" if address.is_global else "public_url_must_use_global_host"


def public_api_url_from_env(values: dict[str, str]) -> str:
    url = values.get("FLOW_MEMORY_PUBLIC_API_URL", "").strip()
    if not url:
        return ""
    if has_placeholder(url):
        return ""
    assert_https_public_url(url)
    return url


def select_managed_redis_url(connection_info: dict[str, Any]) -> str:
    fields = (
        "internalConnectionString",
        "redissConnectionString",
        "tlsConnectionString",
        "externalConnectionString",
        "connectionString",
    )
    schemes: list[dict[str, str]] = []
    for field in fields:
        value = str(connection_info.get(field, "") or "")
        if not value:
            continue
        scheme = url_scheme(value)
        schemes.append({"field": field, "scheme": scheme})
        if scheme in {"redis", "rediss"}:
            return value
    emit(
        "blocked_insecure_redis",
        24,
        required_scheme="rediss_or_render_internal_redis",
        available_connection_schemes=schemes,
        required_action="Render Key Value connection-info must expose an internal redis:// or TLS rediss:// URL before public deployment",
    )
    raise AssertionError("unreachable")


def build_env_vars(
    api_key_value: str,
    database_url: str,
    redis_url: str,
    public_api_url: str = "",
    audit_export_uri: str = "",
    audit_export_object_lock_mode: str = DEFAULT_AUDIT_EXPORT_OBJECT_LOCK_MODE,
    audit_export_retention_days: str = DEFAULT_AUDIT_EXPORT_RETENTION_DAYS,
    audit_export_immutable_required: str = DEFAULT_AUDIT_EXPORT_IMMUTABLE_REQUIRED,
    audit_export_s3_region: str = DEFAULT_AUDIT_EXPORT_S3_REGION,
    audit_export_s3_endpoint_url: str = DEFAULT_AUDIT_EXPORT_S3_ENDPOINT_URL,
    jwt_hs256_secret: str = "",
    jwt_issuer: str = "",
    jwt_audience: str = "",
    jwt_leeway_seconds: str = "60",
    alert_webhook_url: str = "",
    alert_webhook_secret: str = "",
    alert_webhook_timeout_ms: str = "2000",
    error_tracking_webhook_url: str = "",
    error_tracking_webhook_secret: str = "",
    error_tracking_timeout_ms: str = "2000",
    otlp_endpoint_url: str = "",
    otlp_headers: str = "",
    otlp_timeout_ms: str = "5000",
    provider_callback_ip_allowlist: str = "",
) -> list[dict[str, str]]:
    redis_scheme = url_scheme(redis_url)
    redis_is_internal = redis_scheme == "redis"
    if redis_scheme not in {"rediss", "redis"}:
        emit(
            "blocked_insecure_redis",
            24,
            redis_url_scheme=redis_scheme,
            required_scheme="rediss_or_render_internal_redis",
            required_action="FLOW_MEMORY_COMPUTE_REDIS_URL must be a TLS rediss:// URL or Render internal redis:// URL.",
        )
    if url_scheme(database_url) not in {"postgres", "postgresql"}:
        emit(
            "blocked_insecure_postgres",
            25,
            database_url_scheme=url_scheme(database_url),
            required_scheme="postgresql",
            required_action="FLOW_MEMORY_COMPUTE_DATABASE_URL must be a managed PostgreSQL URL.",
        )
    for key, value in (
        ("FLOW_MEMORY_COMPUTE_ALERT_WEBHOOK_URL", alert_webhook_url),
        ("FLOW_MEMORY_COMPUTE_ERROR_TRACKING_WEBHOOK_URL", error_tracking_webhook_url),
        ("FLOW_MEMORY_COMPUTE_OTLP_ENDPOINT_URL", otlp_endpoint_url),
    ):
        assert_https_observability_sink_url(value, key)
    provider_callback_ip_allowlist_from_env(
        {"FLOW_MEMORY_COMPUTE_PROVIDER_CALLBACK_IP_ALLOWLIST": provider_callback_ip_allowlist}
    )
    validate_gateway_jwt_config(jwt_hs256_secret, jwt_issuer, jwt_audience, jwt_leeway_seconds)
    if public_api_url:
        assert_https_public_url(public_api_url)
    values = {
        "FLOW_MEMORY_API_HOST": "0.0.0.0",
        "FLOW_MEMORY_API_PORT": "8765",
        "FLOW_MEMORY_API_KEY": api_key_value,
        "FLOW_MEMORY_API_REQUIRE_SCOPES": "true",
        "FLOW_MEMORY_API_JWT_HS256_SECRET": jwt_hs256_secret,
        "FLOW_MEMORY_API_JWT_ISSUER": jwt_issuer,
        "FLOW_MEMORY_API_JWT_AUDIENCE": jwt_audience,
        "FLOW_MEMORY_API_JWT_LEEWAY_SECONDS": jwt_leeway_seconds,
        "FLOW_MEMORY_API_RATE_LIMIT": "120",
        "FLOW_MEMORY_API_RATE_LIMIT_WINDOW_SECONDS": "60",
        "FLOW_MEMORY_API_MAX_BODY_BYTES": "1048576",
        "FLOW_MEMORY_API_ENABLE_NONCE_CHECK": "true",
        "FLOW_MEMORY_API_MAX_REQUEST_AGE_SECONDS": "300",
        "FLOW_MEMORY_API_NONCE_REPLAY_BACKEND": "redis",
        "FLOW_MEMORY_API_NONCE_REDIS_PREFIX": "flow-memory:api",
        "FLOW_MEMORY_API_NONCE_FAIL_CLOSED": "true",
        "FLOW_MEMORY_API_NONCE_REQUIRE_TLS": "false" if redis_is_internal else "true",
        "FLOW_MEMORY_API_NONCE_VERIFY_TLS": "false" if redis_is_internal else "true",
        "FLOW_MEMORY_LOG_LEVEL": "INFO",
        "FLOW_MEMORY_COMPUTE_METRICS_ENABLED": "true",
        "FLOW_MEMORY_COMPUTE_TRACING_ENABLED": "true",
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
        "FLOW_MEMORY_COMPUTE_ALLOW_INTERNAL_REDIS_IN_PRODUCTION": "true" if redis_is_internal else "false",
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
        "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_OBJECT_LOCK_MODE": audit_export_object_lock_mode,
        "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_RETENTION_DAYS": audit_export_retention_days,
        "FLOW_MEMORY_COMPUTE_AUDIT_CHECKPOINT_INTERVAL_SECONDS": "86400",
        "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_IMMUTABLE_REQUIRED": audit_export_immutable_required,
        "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_S3_REGION": audit_export_s3_region,
        "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_S3_ENDPOINT_URL": audit_export_s3_endpoint_url,
        "FLOW_MEMORY_BILLING_STRIPE_CHECKOUT_ENABLED": "false",
        "FLOW_MEMORY_BILLING_STRIPE_SECRET_KEY": "",
        "FLOW_MEMORY_BILLING_STRIPE_SUCCESS_URL": "",
        "FLOW_MEMORY_BILLING_STRIPE_CANCEL_URL": "",
        "FLOW_MEMORY_BILLING_STRIPE_CHECKOUT_TIMEOUT_MS": "5000",
        "FLOW_MEMORY_BILLING_STRIPE_API_BASE_URL": "https://api.stripe.com",
        "FLOW_MEMORY_BILLING_STRIPE_PRODUCT_NAME": "Flow Memory compute credits",
        "FLOW_MEMORY_BILLING_STRIPE_WEBHOOK_SECRET": "",
        "FLOW_MEMORY_BILLING_STRIPE_WEBHOOK_TOLERANCE_SECONDS": DEFAULT_STRIPE_WEBHOOK_TOLERANCE_SECONDS,
        "FLOW_MEMORY_COMPUTE_ALERT_ROUTING_ENABLED": "true" if alert_webhook_url else "false",
        "FLOW_MEMORY_COMPUTE_ALERT_WEBHOOK_URL": alert_webhook_url,
        "FLOW_MEMORY_COMPUTE_ALERT_WEBHOOK_SECRET": alert_webhook_secret,
        "FLOW_MEMORY_COMPUTE_ALERT_WEBHOOK_TIMEOUT_MS": alert_webhook_timeout_ms,
        "FLOW_MEMORY_COMPUTE_ERROR_TRACKING_ENABLED": "true" if error_tracking_webhook_url else "false",
        "FLOW_MEMORY_COMPUTE_ERROR_TRACKING_WEBHOOK_URL": error_tracking_webhook_url,
        "FLOW_MEMORY_COMPUTE_ERROR_TRACKING_WEBHOOK_SECRET": error_tracking_webhook_secret,
        "FLOW_MEMORY_COMPUTE_ERROR_TRACKING_TIMEOUT_MS": error_tracking_timeout_ms,
        "FLOW_MEMORY_COMPUTE_TELEMETRY_EXPORT_ENABLED": "true" if otlp_endpoint_url else "false",
        "FLOW_MEMORY_COMPUTE_OTLP_ENDPOINT_URL": otlp_endpoint_url,
        "FLOW_MEMORY_COMPUTE_OTLP_HEADERS": otlp_headers,
        "FLOW_MEMORY_COMPUTE_OTLP_TIMEOUT_MS": otlp_timeout_ms,
        "FLOW_MEMORY_COMPUTE_EXTERNAL_QUOTES_ENABLED": "false",
        "FLOW_MEMORY_COMPUTE_EXTERNAL_PROVIDER_ALLOWLIST": "",
        "FLOW_MEMORY_COMPUTE_PROVIDER_CALLBACK_IP_ALLOWLIST": provider_callback_ip_allowlist,
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
    *,
    plan: str | None = None,
    enable_disk: bool | None = None,
) -> dict[str, Any]:
    plan = DEFAULT_SERVICE_PLAN if plan is None else plan
    enable_disk = ENABLE_RENDER_DISK if enable_disk is None else enable_disk
    existing = find_named(api_key, "/services", "service", owner_id, SERVICE_NAME)
    service_details = {
        "runtime": "docker",
        "plan": plan,
        "region": region,
        "numInstances": 1,
        "healthCheckPath": "/healthz",
        "envSpecificDetails": {
            "dockerfilePath": "./Dockerfile.compute-market",
            "dockerContext": ".",
            "dockerCommand": "flow-memory-api --host 0.0.0.0 --port 8765 --require-scopes",
        },
    }
    if enable_disk:
        service_details["disk"] = _service_disk_details()
    if existing is not None:
        service_id = str(existing["id"])
        render_request(
            api_key,
            "PATCH",
            f"/services/{urllib.parse.quote(service_id)}",
            {
                "branch": branch,
                "repo": repo,
                "autoDeploy": "no",
                "serviceDetails": {
                    "runtime": "docker",
                    "plan": plan,
                    "healthCheckPath": "/healthz",
                    "envSpecificDetails": service_details["envSpecificDetails"],
                },
            },
        )
        if enable_disk:
            ensure_service_disk(api_key, service_id)
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


def assert_https_public_url(url: str) -> None:
    if not url.startswith("https://"):
        emit(
            "failed_deployment",
            33,
            public_url=url,
            reason="public_url_must_use_https_tls",
            required_action="configure a Render public HTTPS URL or custom domain with TLS before smoke tests",
        )
    block_reason = public_url_block_reason(url)
    if block_reason:
        emit(
            "failed_deployment",
            33,
            public_url=url,
            reason=block_reason,
            required_action="configure a public Render URL or custom domain that resolves outside loopback/local/private networks",
        )


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


def call_text(method: str, url: str, headers: dict[str, str] | None = None) -> tuple[int, str]:
    req = urllib.request.Request(url, headers=dict(headers or {}), method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except (TimeoutError, urllib.error.URLError, OSError) as exc:
        return 0, str(exc)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def gateway_jwt_bearer_token(secret: str, issuer: str, audience: str, scopes: str) -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    claims = {
        "sub": "render-public-smoke",
        "iss": issuer,
        "aud": audience,
        "iat": now,
        "exp": now + 300,
        "scope": scopes,
    }
    signing_input = ".".join(
        (
            _b64url(json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")),
            _b64url(json.dumps(claims, separators=(",", ":"), sort_keys=True).encode("utf-8")),
        )
    )
    signature = hmac.new(secret.encode("utf-8"), signing_input.encode("ascii"), "sha256").digest()
    return f"{signing_input}.{_b64url(signature)}"


def _smoke_nonce_headers(headers: dict[str, str], label: str) -> dict[str, str]:
    nonce_headers = dict(headers)
    nonce_headers["x-flow-memory-timestamp"] = str(time.time())
    nonce_headers["x-flow-memory-nonce"] = f"{label}-{secrets.token_urlsafe(18)}"
    return nonce_headers


def _smoke_api_headers(api_key_value: str, scopes: str, label: str) -> dict[str, str]:
    return _smoke_nonce_headers(
        {"x-flow-memory-api-key": api_key_value, "x-flow-memory-scopes": scopes},
        label,
    )


def smoke_public(
    base_url: str,
    api_key_value: str,
    gateway_jwt: dict[str, str] | None = None,
) -> dict[str, Any]:
    base = base_url.rstrip("/")
    if not base.startswith("https://"):
        return {
            "ok": False,
            "statuses": {},
            "public_url": base,
            "reason": "public_url_must_use_https_tls",
        }
    block_reason = public_url_block_reason(base)
    if block_reason:
        return {
            "ok": False,
            "statuses": {},
            "public_url": base,
            "reason": block_reason,
        }
    plan_body = {"task": "public live Level 1 Flow Memory Compute Market smoke test", "dry_run": True}
    checks: dict[str, Any] = {}
    checks["root"] = call_json("GET", f"{base}/")
    checks["health"] = call_json("GET", f"{base}/compute/health", _smoke_api_headers(api_key_value, "compute:read", "health"))
    checks["readiness"] = call_json("GET", f"{base}/compute/readiness", _smoke_api_headers(api_key_value, "compute:read", "readiness"))
    checks["plan"] = call_json("POST", f"{base}/compute/plan", _smoke_api_headers(api_key_value, "compute:plan", "plan"), plan_body)
    checks["metrics"] = call_text("GET", f"{base}/metrics", _smoke_api_headers(api_key_value, "compute:read", "metrics"))
    checks["alerts"] = call_json("GET", f"{base}/compute/alerts", _smoke_api_headers(api_key_value, "compute:read", "alerts"))
    checks["telemetry"] = call_json("GET", f"{base}/compute/telemetry", _smoke_api_headers(api_key_value, "compute:read", "telemetry"))
    checks["audit_verify"] = call_json("GET", f"{base}/compute/audit/verify", _smoke_api_headers(api_key_value, "compute:audit", "audit-verify"))
    checks["admin_audit_export"] = call_json("GET", f"{base}/admin/audit/export", _smoke_api_headers(api_key_value, "compute:admin", "audit-export"))
    checks["audit_export_write"] = call_json("POST", f"{base}/compute/audit/export", _smoke_api_headers(api_key_value, "compute:audit", "audit-export-write"), {"chain_id": "all"})
    checks["admin_storage_diagnostics"] = call_json("GET", f"{base}/admin/storage/diagnostics", _smoke_api_headers(api_key_value, "compute:admin", "storage-diagnostics"))
    checks["admin_redis_diagnostics"] = call_json("GET", f"{base}/admin/redis/diagnostics", _smoke_api_headers(api_key_value, "compute:admin", "redis-diagnostics"))
    checks["missing_key"] = call_json("GET", f"{base}/compute/health", {"x-flow-memory-scopes": "compute:read"})
    checks["wrong_scope"] = call_json("POST", f"{base}/compute/plan", _smoke_api_headers(api_key_value, "compute:read", "wrong-scope"), plan_body)
    jwt_secret = str((gateway_jwt or {}).get("FLOW_MEMORY_API_JWT_HS256_SECRET", ""))
    if jwt_secret:
        jwt_issuer = str((gateway_jwt or {}).get("FLOW_MEMORY_API_JWT_ISSUER", ""))
        jwt_audience = str((gateway_jwt or {}).get("FLOW_MEMORY_API_JWT_AUDIENCE", ""))
        jwt_scopes = "compute:read compute:plan compute:audit compute:admin"
        jwt_token = gateway_jwt_bearer_token(jwt_secret, jwt_issuer, jwt_audience, jwt_scopes)
        bad_jwt_token = gateway_jwt_bearer_token(jwt_secret, jwt_issuer, f"{jwt_audience}-wrong", jwt_scopes)
        checks["jwt_health"] = call_json(
            "GET",
            f"{base}/compute/health",
            _smoke_nonce_headers({"authorization": f"Bearer {jwt_token}", "x-flow-memory-scopes": "compute:read"}, "jwt-health"),
        )
        checks["jwt_wrong_audience"] = call_json(
            "GET",
            f"{base}/compute/health",
            _smoke_nonce_headers(
                {"authorization": f"Bearer {bad_jwt_token}", "x-flow-memory-scopes": "compute:read"},
                "jwt-wrong-audience",
            ),
        )
    health_ok = checks["health"][0] == 200 and checks["health"][1].get("ok") is True
    readiness_payload = checks["readiness"][1].get("data", {}) if isinstance(checks["readiness"][1], dict) else {}
    safety = readiness_payload.get("production_safety_defaults", {})
    storage = readiness_payload.get("storage", {})
    plan_payload = checks["plan"][1].get("data", {}).get("compute_plan", {}) if isinstance(checks["plan"][1], dict) else {}
    audit_ok = checks["audit_verify"][0] == 200 and checks["audit_verify"][1].get("ok") is True
    root_payload = checks["root"][1].get("data", {}) if isinstance(checks["root"][1], dict) else {}
    audit_export_payload = checks["admin_audit_export"][1].get("data", {}) if isinstance(checks["admin_audit_export"][1], dict) else {}
    audit_export_write_payload = checks["audit_export_write"][1].get("data", {}) if isinstance(checks["audit_export_write"][1], dict) else {}
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
            safety.get("redis_url_scheme") == "rediss"
            or (safety.get("redis_url_scheme") == "redis" and safety.get("allow_internal_redis_in_production") is True),
            checks["plan"][0] == 200,
            plan_payload.get("dry_run_only") is True,
            plan_payload.get("funds_moved") is False,
            plan_payload.get("broadcast_allowed") is False,
            plan_payload.get("private_key_required") is False,
            checks["metrics"][0] == 200,
            "compute_plan_requests_total" in str(checks["metrics"][1]),
            checks["alerts"][0] == 200,
            checks["alerts"][1].get("ok") is True,
            checks["telemetry"][0] == 200,
            checks["telemetry"][1].get("ok") is True,
            (not jwt_secret or checks["jwt_health"][0] == 200),
            (not jwt_secret or checks["jwt_health"][1].get("ok") is True),
            (not jwt_secret or checks["jwt_wrong_audience"][0] == 401),
            audit_ok,
            checks["admin_audit_export"][0] == 200,
            checks["audit_export_write"][0] == 200,
            audit_export_write_payload.get("ok") is True,
            bool(audit_export_write_payload.get("manifest_hash")),
            int(audit_export_write_payload.get("event_count", 0) or 0) >= 1,
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
            audit_export_payload.get("immutable") is True
            or audit_export_payload.get("audit_exporter_status", {}).get("exporter") == "local_file",
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
        "audit_export_write": checks["audit_export_write"][0],
        "audit_export_write_manifest_hash_present": bool(audit_export_write_payload.get("manifest_hash")),
        "admin_storage_diagnostics": checks["admin_storage_diagnostics"][0],
        "admin_redis_diagnostics": checks["admin_redis_diagnostics"][0],
        "redis_url_scheme": safety.get("redis_url_scheme"),
        "metrics": checks["metrics"][0],
        "alerts": checks["alerts"][0],
        "telemetry": checks["telemetry"][0],
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
    parser.add_argument("--allow-free-plans", action="store_true", default=False)
    parser.add_argument("--api-key", default=os.environ.get("RENDER_API_KEY", ""))
    parser.add_argument("--owner-id", default=os.environ.get("RENDER_OWNER_ID", ""))
    parser.add_argument("--region", default=os.environ.get("RENDER_REGION", ""))
    parser.add_argument("--branch", default=os.environ.get("RENDER_BRANCH", ""))
    parser.add_argument("--repo-url", default=os.environ.get("RENDER_REPO_URL", ""))
    args = parser.parse_args()
    env_values = parse_env(Path(args.env_file))
    render_api_key = args.api_key or env_values.get("RENDER_API_KEY", "")
    render_owner_id = args.owner_id or env_values.get("RENDER_OWNER_ID", "")
    render_region = args.region or env_values.get("RENDER_REGION", "oregon")
    render_branch = args.branch or env_values.get("RENDER_BRANCH", "")
    render_repo_url = args.repo_url or env_values.get("RENDER_REPO_URL", "")
    render_postgres_plan = env_values.get("RENDER_POSTGRES_PLAN", "") or DEFAULT_POSTGRES_PLAN
    render_keyvalue_plan = env_values.get("RENDER_KEYVALUE_PLAN", "") or DEFAULT_KEYVALUE_PLAN
    render_service_plan = env_values.get("RENDER_SERVICE_PLAN", "") or DEFAULT_SERVICE_PLAN
    render_keyvalue_ip_allowlist = env_values.get("RENDER_KEYVALUE_IP_ALLOWLIST", "") or DEFAULT_KEYVALUE_IP_ALLOWLIST
    if has_placeholder(render_owner_id):
        render_owner_id = ""
    if has_placeholder(render_repo_url):
        render_repo_url = ""
    if has_placeholder(render_keyvalue_ip_allowlist):
        render_keyvalue_ip_allowlist = DEFAULT_KEYVALUE_IP_ALLOWLIST
    render_enable_disk = _bool_setting(env_values, "RENDER_ENABLE_DISK", ENABLE_RENDER_DISK)
    render_allow_free_plans = args.allow_free_plans or _bool_setting(env_values, "RENDER_ALLOW_FREE_PLANS", ALLOW_FREE_RENDER_PLANS)

    if not render_api_key or has_placeholder(render_api_key):
        emit("blocked_missing_render_auth", 20, missing_values=["RENDER_API_KEY"])
    validate_render_plans(
        postgres_plan=render_postgres_plan,
        keyvalue_plan=render_keyvalue_plan,
        service_plan=render_service_plan,
        allow_free=render_allow_free_plans,
    )
    assert_level1_safety_settings(env_values)
    audit_export_uri = audit_export_uri_from_env(env_values)
    audit_export_s3_region = audit_export_s3_region_from_env(env_values, audit_export_uri)
    audit_export_object_lock_mode = _audit_export_setting(
        env_values,
        "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_OBJECT_LOCK_MODE",
        DEFAULT_AUDIT_EXPORT_OBJECT_LOCK_MODE,
    )
    audit_export_retention_days = _audit_export_setting(
        env_values,
        "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_RETENTION_DAYS",
        DEFAULT_AUDIT_EXPORT_RETENTION_DAYS,
    )
    audit_export_immutable_required = _audit_export_setting(
        env_values,
        "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_IMMUTABLE_REQUIRED",
        DEFAULT_AUDIT_EXPORT_IMMUTABLE_REQUIRED,
    )
    if not audit_export_uri.startswith("s3://"):
        audit_export_object_lock_mode = ""
        audit_export_retention_days = "0"
        audit_export_immutable_required = "false"
        render_enable_disk = True
    audit_export_s3_endpoint_url = _audit_export_setting(
        env_values,
        "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_S3_ENDPOINT_URL",
        DEFAULT_AUDIT_EXPORT_S3_ENDPOINT_URL,
    )
    alert_webhook_url = observability_sink_url_from_env(
        env_values,
        "FLOW_MEMORY_COMPUTE_ALERT_WEBHOOK_URL",
        "FLOW_MEMORY_COMPUTE_ALERT_ROUTING_ENABLED",
    )
    error_tracking_webhook_url = observability_sink_url_from_env(
        env_values,
        "FLOW_MEMORY_COMPUTE_ERROR_TRACKING_WEBHOOK_URL",
        "FLOW_MEMORY_COMPUTE_ERROR_TRACKING_ENABLED",
    )
    otlp_endpoint_url = observability_sink_url_from_env(
        env_values,
        "FLOW_MEMORY_COMPUTE_OTLP_ENDPOINT_URL",
        "FLOW_MEMORY_COMPUTE_TELEMETRY_EXPORT_ENABLED",
    )
    alert_webhook_secret = _env_setting(env_values, "FLOW_MEMORY_COMPUTE_ALERT_WEBHOOK_SECRET")
    error_tracking_webhook_secret = _env_setting(env_values, "FLOW_MEMORY_COMPUTE_ERROR_TRACKING_WEBHOOK_SECRET")
    otlp_headers = _env_setting(env_values, "FLOW_MEMORY_COMPUTE_OTLP_HEADERS")
    alert_webhook_timeout_ms = _env_setting(env_values, "FLOW_MEMORY_COMPUTE_ALERT_WEBHOOK_TIMEOUT_MS", "2000")
    error_tracking_timeout_ms = _env_setting(
        env_values,
        "FLOW_MEMORY_COMPUTE_ERROR_TRACKING_TIMEOUT_MS",
        "2000",
    )
    otlp_timeout_ms = _env_setting(env_values, "FLOW_MEMORY_COMPUTE_OTLP_TIMEOUT_MS", "5000")
    provider_callback_ip_allowlist = provider_callback_ip_allowlist_from_env(env_values)
    gateway_jwt = gateway_jwt_config_from_env(env_values)
    configured_public_api_url = public_api_url_from_env(env_values)
    owner_id = infer_owner_id(render_api_key, render_owner_id)

    api_key_value = env_values.get("FLOW_MEMORY_API_KEY", "")
    if not api_key_value or has_placeholder(api_key_value):
        existing_service = find_named(render_api_key, "/services", "service", owner_id, SERVICE_NAME)
        existing_api_key = (
            service_env_value(render_api_key, str(existing_service["id"]), "FLOW_MEMORY_API_KEY")
            if existing_service is not None
            else ""
        )
        api_key_value = (
            existing_api_key
            if existing_api_key and not has_placeholder(existing_api_key)
            else "fmk_live_" + secrets.token_urlsafe(48)
        )

    branch = render_branch or current_branch()
    repo = render_repo_url or public_repo_url()
    assert_branch_is_publishable(branch)

    try:
        postgres = ensure_postgres(render_api_key, owner_id, render_region, plan=render_postgres_plan)
        keyvalue = ensure_keyvalue(
            render_api_key,
            owner_id,
            render_region,
            plan=render_keyvalue_plan,
            ip_allowlist=render_keyvalue_ip_allowlist,
        )
        postgres = wait_available(render_api_key, "/postgres", str(postgres["id"]), "postgres")
        keyvalue = wait_available(render_api_key, "/key-value", str(keyvalue["id"]), "keyvalue")
        pg_conn = render_request(render_api_key, "GET", f"/postgres/{urllib.parse.quote(str(postgres['id']))}/connection-info")
        kv_conn = render_request(render_api_key, "GET", f"/key-value/{urllib.parse.quote(str(keyvalue['id']))}/connection-info")
        redis_url = select_managed_redis_url(kv_conn)
        env_vars = build_env_vars(
            api_key_value,
            str(pg_conn["internalConnectionString"]),
            redis_url,
            public_api_url=configured_public_api_url,
            audit_export_uri=audit_export_uri,
            audit_export_s3_region=audit_export_s3_region,
            audit_export_object_lock_mode=audit_export_object_lock_mode,
            audit_export_retention_days=audit_export_retention_days,
            audit_export_immutable_required=audit_export_immutable_required,
            audit_export_s3_endpoint_url=audit_export_s3_endpoint_url,
            jwt_hs256_secret=gateway_jwt["FLOW_MEMORY_API_JWT_HS256_SECRET"],
            jwt_issuer=gateway_jwt["FLOW_MEMORY_API_JWT_ISSUER"],
            jwt_audience=gateway_jwt["FLOW_MEMORY_API_JWT_AUDIENCE"],
            jwt_leeway_seconds=gateway_jwt["FLOW_MEMORY_API_JWT_LEEWAY_SECONDS"],
            alert_webhook_url=alert_webhook_url,
            alert_webhook_secret=alert_webhook_secret,
            alert_webhook_timeout_ms=alert_webhook_timeout_ms,
            error_tracking_webhook_url=error_tracking_webhook_url,
            error_tracking_webhook_secret=error_tracking_webhook_secret,
            error_tracking_timeout_ms=error_tracking_timeout_ms,
            otlp_endpoint_url=otlp_endpoint_url,
            otlp_headers=otlp_headers,
            otlp_timeout_ms=otlp_timeout_ms,
            provider_callback_ip_allowlist=provider_callback_ip_allowlist,
        )
        service = ensure_service(render_api_key, owner_id, render_region, repo, branch, env_vars, plan=render_service_plan, enable_disk=render_enable_disk)
        url = public_url(service)
        if not url:
            service = render_request(render_api_key, "GET", f"/services/{urllib.parse.quote(str(service['id']))}")
            url = public_url(service)
        if not url:
            emit("failed_deployment", 33, public_url="", reason="render_service_url_missing")
        deployment_public_url = url
        assert_https_public_url(deployment_public_url)
        env_vars = build_env_vars(
            api_key_value,
            str(pg_conn["internalConnectionString"]),
            redis_url,
            public_api_url=deployment_public_url,
            audit_export_uri=audit_export_uri,
            audit_export_s3_region=audit_export_s3_region,
            audit_export_object_lock_mode=audit_export_object_lock_mode,
            audit_export_retention_days=audit_export_retention_days,
            audit_export_immutable_required=audit_export_immutable_required,
            audit_export_s3_endpoint_url=audit_export_s3_endpoint_url,
            jwt_hs256_secret=gateway_jwt["FLOW_MEMORY_API_JWT_HS256_SECRET"],
            jwt_issuer=gateway_jwt["FLOW_MEMORY_API_JWT_ISSUER"],
            jwt_audience=gateway_jwt["FLOW_MEMORY_API_JWT_AUDIENCE"],
            jwt_leeway_seconds=gateway_jwt["FLOW_MEMORY_API_JWT_LEEWAY_SECONDS"],
            alert_webhook_url=alert_webhook_url,
            alert_webhook_secret=alert_webhook_secret,
            alert_webhook_timeout_ms=alert_webhook_timeout_ms,
            error_tracking_webhook_url=error_tracking_webhook_url,
            error_tracking_webhook_secret=error_tracking_webhook_secret,
            error_tracking_timeout_ms=error_tracking_timeout_ms,
            otlp_endpoint_url=otlp_endpoint_url,
            otlp_headers=otlp_headers,
            otlp_timeout_ms=otlp_timeout_ms,
            provider_callback_ip_allowlist=provider_callback_ip_allowlist,
        )
        render_request(render_api_key, "PUT", f"/services/{urllib.parse.quote(str(service['id']))}/env-vars", env_vars)
        trigger_service_deploy(render_api_key, str(service["id"]))
        last_smoke: dict[str, Any] | None = None
        for _ in range(90):
            last_smoke = smoke_public(deployment_public_url, api_key_value, gateway_jwt)
            if last_smoke.get("ok") is True:
                emit(
                    "public_level_1_live",
                    0,
                    public_url=deployment_public_url,
                    postgres=f"managed_render_postgres:{render_postgres_plan}",
                    redis=f"managed_render_keyvalue:{render_keyvalue_plan}",
                    service_plan=render_service_plan,
                    audit_export_storage="s3_object_lock" if audit_export_uri.startswith("s3://") else "render_disk_local_file",
                    smoke="passed",
                    live_settlement_enabled=False,
                    funds_moved=False,
                    private_keys_accepted=False,
                    broadcast_enabled=False,
                )
            time.sleep(10)
        emit("failed_public_smoke_tests", 34, public_url=deployment_public_url, smoke=last_smoke or {})
    except RenderError as exc:
        status = "blocked_render_payment_or_permission" if exc.status in {401, 402, 403} else "failed_deployment"
        emit(status, 40, render_status=exc.status, render_message=exc.message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
