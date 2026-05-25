from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Mapping


PUBLIC_TASK = "Flow Memory Compute Market public production buildout validation"


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


def call_json(method: str, url: str, headers: Mapping[str, str] | None = None, body: Mapping[str, Any] | None = None) -> tuple[int, Mapping[str, Any]]:
    data = None
    request_headers = dict(headers or {})
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


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def data(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    value = payload.get("data", {})
    return value if isinstance(value, Mapping) else {}


def validate(base_url: str, api_key: str) -> Mapping[str, Any]:
    base = base_url.rstrip("/")
    headers_read = {"x-flow-memory-api-key": api_key, "x-flow-memory-scopes": "compute:read"}
    headers_plan = {"x-flow-memory-api-key": api_key, "x-flow-memory-scopes": "compute:plan"}
    headers_audit = {"x-flow-memory-api-key": api_key, "x-flow-memory-scopes": "compute:audit"}
    headers_provider = {"x-flow-memory-api-key": api_key, "x-flow-memory-scopes": "compute:provider-admin"}
    headers_execute = {"x-flow-memory-api-key": api_key, "x-flow-memory-scopes": "compute:execute"}
    headers_billing = {"x-flow-memory-api-key": api_key, "x-flow-memory-scopes": "compute:billing"}
    headers_admin = {"x-flow-memory-api-key": api_key, "x-flow-memory-scopes": "compute:admin"}

    checks: dict[str, tuple[int, Mapping[str, Any]]] = {}
    checks["root"] = call_json("GET", f"{base}/")
    checks["health"] = call_json("GET", f"{base}/compute/health", headers_read)
    checks["readiness"] = call_json("GET", f"{base}/compute/readiness", headers_read)
    checks["plan"] = call_json("POST", f"{base}/compute/plan", headers_plan, {"task": PUBLIC_TASK, "dry_run": True})
    checks["audit_verify"] = call_json("GET", f"{base}/compute/audit/verify", headers_audit)
    checks["missing_key"] = call_json("GET", f"{base}/compute/health", {"x-flow-memory-scopes": "compute:read"})
    checks["wrong_scope"] = call_json("POST", f"{base}/compute/plan", headers_read, {"task": PUBLIC_TASK, "dry_run": True})

    suffix = str(int(time.time()))
    provider_id = f"provider_public_buildout_{suffix}"
    route_id = f"route_public_buildout_{suffix}"
    provider = {
        "provider_id": provider_id,
        "provider_name": "Public Buildout Validation Provider",
        "provider_type": "gpu",
        "supported_unit_types": ["gpu_minute", "gpu_hour", "request"],
        "supported_assets": ["USD", "USDC", "CREDITS"],
        "supported_networks": ["offchain", "solana", "base"],
        "quote_endpoint": "https://provider.example.com/quote",
        "health_endpoint": "https://provider.example.com/health",
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
    checks["job_complete"] = call_json(
        "POST",
        f"{base}/compute/jobs/{job_id}/complete",
        headers_execute,
        {
            "actual_units": 2,
            "actual_total_cost": 0.18,
            "currency": "USD",
            "artifact_ref": "s3://flow-memory-results/public-buildout-validation.json",
            "artifact_data": {"result": "ok"},
        },
    )
    checks["job_artifacts"] = call_json("GET", f"{base}/compute/jobs/{job_id}/artifacts", headers_read)
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
    checks["telemetry"] = call_json("GET", f"{base}/compute/telemetry", headers_read)
    checks["metrics"] = call_json("GET", f"{base}/compute/metrics", headers_read)
    checks["alerts"] = call_json("GET", f"{base}/compute/alerts", headers_read)
    checks["billing_checkout"] = call_json("POST", f"{base}/billing/checkout", headers_billing, {"account_id": f"acct_public_buildout_{suffix}", "amount": 100, "currency": "USD"})
    checks["billing_balance"] = call_json("GET", f"{base}/billing/balance?account_id=acct_public_buildout_{suffix}", headers_billing)
    checks["billing_refund"] = call_json(
        "POST",
        f"{base}/billing/refund",
        headers_billing,
        {
            "account_id": f"acct_public_buildout_{suffix}",
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

    root_data = data(checks["root"][1])
    readiness = data(checks["readiness"][1])
    plan = data(checks["plan"][1]).get("compute_plan", {})
    job = data(checks["job_create"][1]).get("job", {})
    checkout = data(checks["billing_checkout"][1]).get("checkout", {})
    refund = data(checks["billing_refund"][1]).get("refund", {})
    storage_diag = data(checks["admin_storage_diagnostics"][1])
    redis_diag = data(checks["admin_redis_diagnostics"][1])

    require(checks["root"][0] == 200 and root_data.get("service") == "Flow Memory Compute Market", "root public landing failed")
    require(checks["health"][0] == 200 and data(checks["health"][1]).get("ok") is True, "health failed")
    require(checks["readiness"][0] == 200 and readiness.get("ready") is True, "readiness failed")
    require(readiness.get("storage", {}).get("backend") in {"postgres", "postgresql"}, "readiness did not report Postgres")
    require(readiness.get("rate_limiter_status", {}).get("backend") == "redis" or readiness.get("production_safety_defaults", {}).get("rate_limit_backend") == "redis", "readiness did not report Redis limiter")
    require(readiness.get("circuit_breaker_status", {}).get("backend") == "redis" or readiness.get("production_safety_defaults", {}).get("circuit_breaker_backend") == "redis", "readiness did not report Redis circuit breaker")
    require(plan.get("dry_run_only") is True and plan.get("funds_moved") is False and plan.get("broadcast_allowed") is False and plan.get("private_key_required") is False, "plan safety flags failed")
    require(checks["audit_verify"][0] == 200 and data(checks["audit_verify"][1]).get("ok") is True, "audit verify failed")
    require(checks["missing_key"][0] == 401, "missing key did not fail")
    require(checks["wrong_scope"][0] == 403, "wrong scope did not fail")
    require(checks["external_quote_disabled"][0] == 200 and data(checks["external_quote_disabled"][1]).get("ok") is False, "external quote endpoint did not fail closed")
    require(checks["job_receipt_wrong_scope"][0] == 403, "receipt endpoint wrong scope did not fail")
    require(checks["job_receipt_unsigned"][0] == 200 and data(checks["job_receipt_unsigned"][1]).get("ok") is False, "unsigned provider receipt did not fail closed")
    for name in ("provider_apply", "provider_verify", "provider_conformance", "provider_get", "capacity_list", "capacity_reserve", "capacity_release", "quote_ingest", "prices", "job_create", "job_get", "job_events", "job_dispatch", "job_complete", "job_artifacts", "job_fail_create", "job_fail", "job_retry_create", "job_retry", "job_cancel", "telemetry", "metrics", "alerts"):
        require(checks[name][0] == 200 and checks[name][1].get("ok") is True, f"{name} failed")
    require(job.get("dry_run_only") is True and job.get("funds_moved") is False and job.get("broadcast_allowed") is False and job.get("private_key_required") is False, "job safety flags failed")
    require(checks["billing_checkout"][0] == 200 and checkout.get("funds_moved") is False and checkout.get("status") == "requires_external_checkout_provider", "billing checkout safety failed")
    require(checks["billing_balance"][0] == 200 and data(checks["billing_balance"][1]).get("balance", {}).get("account_id") == f"acct_public_buildout_{suffix}", "billing balance failed")
    require(checks["billing_refund"][0] == 200 and refund.get("funds_moved") is False and refund.get("external_refund_created") is False and refund.get("status") == "recorded_no_custody", "billing refund safety failed")
    require(checks["admin_reconciliation"][0] == 200 and checks["admin_reconciliation"][1].get("ok") is True, "admin reconciliation failed")
    require(checks["admin_storage_diagnostics"][0] == 200 and storage_diag.get("ok") is True and storage_diag.get("production_readiness", {}).get("production_ready") is True, "admin storage diagnostics failed")
    require(checks["admin_redis_diagnostics"][0] == 200 and redis_diag.get("ok") is True and redis_diag.get("rate_limit_probe", {}).get("ok") is True and redis_diag.get("circuit_breaker_probe", {}).get("ok") is True, "admin redis diagnostics failed")
    require(checks["admin_audit_export"][0] == 200 and "audit_exporter_status" in data(checks["admin_audit_export"][1]), "admin audit export status failed")

    return {
        "status": "passed",
        "public_url": base,
        "checks": {name: status for name, (status, _payload) in sorted(checks.items())},
        "storage_backend": readiness.get("storage", {}).get("backend"),
        "rate_limit_backend": readiness.get("rate_limiter_status", {}).get("backend") or readiness.get("production_safety_defaults", {}).get("rate_limit_backend"),
        "circuit_breaker_backend": readiness.get("circuit_breaker_status", {}).get("backend") or readiness.get("production_safety_defaults", {}).get("circuit_breaker_backend"),
        "dry_run_only": True,
        "funds_moved": False,
        "broadcast_allowed": False,
        "private_key_required": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Flow Memory Compute Market public production buildout")
    parser.add_argument("--api-url", default="")
    parser.add_argument("--env-file", default=".env.compute-market.live")
    args = parser.parse_args(argv)

    env_values = parse_env_file(Path(args.env_file))
    api_url = args.api_url or env_values.get("FLOW_MEMORY_PUBLIC_API_URL", "")
    api_key = env_values.get("FLOW_MEMORY_API_KEY", "")
    if not api_url.startswith("https://"):
        raise SystemExit("FLOW_MEMORY_PUBLIC_API_URL/--api-url must be an https:// URL")
    if not api_key:
        raise SystemExit("FLOW_MEMORY_API_KEY is required in the env file")
    result = validate(api_url, api_key)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
