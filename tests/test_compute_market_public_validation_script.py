from __future__ import annotations

from typing import Any, Mapping

import scripts.validate_compute_market_public_buildout as validator


def test_public_buildout_validation_checks_unsigned_provider_receipts(monkeypatch: Any) -> None:
    calls: list[tuple[str, str, Mapping[str, str] | None, Mapping[str, Any] | None]] = []
    job_counter = 0

    def fake_call_json(
        method: str,
        url: str,
        headers: Mapping[str, str] | None = None,
        body: Mapping[str, Any] | None = None,
    ) -> tuple[int, Mapping[str, Any]]:
        nonlocal job_counter
        calls.append((method, url, headers, body))
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
        if url.endswith("/billing/checkout"):
            return 200, {
                "ok": True,
                "data": {"checkout": {"funds_moved": False, "status": "requires_external_checkout_provider"}},
            }
        if "/billing/balance" in url:
            return 200, {"ok": True, "data": {"balance": {"account_id": "acct_public_buildout_1234567890"}}}
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
                    "schema_verification": {
                        "ok": True,
                        "missing_tables": [],
                        "missing_indexes": [],
                        "advisory_lock_probe": {"acquired": True},
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

    monkeypatch.setattr(validator.time, "time", lambda: 1234567890)
    monkeypatch.setattr(validator, "call_json", fake_call_json)

    result = validator.validate("https://api.example.test", "prod-key", require_immutable_audit=True)

    receipt_calls = [call for call in calls if call[1].endswith("/receipt")]
    assert result["status"] == "passed"
    assert result["checks"]["job_receipt_wrong_scope"] == 403
    assert result["checks"]["job_receipt_unsigned"] == 200
    assert result["audit_export_immutable"] is True
    assert result["require_managed_redis_in_production"] is True
    assert result["redis_url_scheme"] == "rediss"
    assert len(receipt_calls) == 2
    refund_calls = [call for call in calls if call[1].endswith("/billing/refund")]
    assert len(refund_calls) == 1
    assert refund_calls[0][2] is not None and refund_calls[0][2]["x-flow-memory-scopes"] == "compute:billing"
    assert refund_calls[0][3] is not None
    assert refund_calls[0][3]["amount"] == 1
    assert receipt_calls[0][2] is not None and receipt_calls[0][2]["x-flow-memory-scopes"] == "compute:read"
    assert receipt_calls[1][2] is not None and receipt_calls[1][2]["x-flow-memory-scopes"] == "compute:execute"
    assert receipt_calls[1][3] is not None
    assert "signature" not in receipt_calls[1][3]
    assert receipt_calls[1][3]["receipt"]["funds_moved"] is False
