from __future__ import annotations

from typing import Any, Mapping

import scripts.validate_compute_market_public_buildout as validator


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

def test_public_buildout_main_accepts_require_immutable_audit_flag(tmp_path: Any, monkeypatch: Any) -> None:
    env_file = tmp_path / "live.env"
    env_file.write_text("FLOW_MEMORY_API_KEY=prod-key\n", encoding="utf-8")
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
        "api_key": "prod-key",
        "require_immutable_audit": True,
    }


def test_public_url_block_reason_rejects_placeholder_domains() -> None:
    blocked = (
        "https://api.yourdomain.com",
        "https://example.com",
        "https://compute.<your-domain>",
        "https://changeme.flowmemory.invalid",
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


def test_public_buildout_validation_checks_unsigned_provider_receipts(monkeypatch: Any) -> None:
    calls: list[tuple[str, str, Mapping[str, str] | None, Mapping[str, Any] | None]] = []
    job_counter = 0
    text_calls: list[tuple[str, str, Mapping[str, str] | None]] = []

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
                        "require_managed_sql_in_production": True,
                        "dry_run_required": True,
                        "live_settlement_enabled": False,
                        "broadcast_enabled": False,
                        "private_key_inputs_allowed": False,
                        "audit_required": True,
                        "audit_export_required": True,
                        "audit_export_immutable_required": True,
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

    result = validator.validate("https://api.example.test", "prod-key", require_immutable_audit=True)

    receipt_calls = [call for call in calls if call[1].endswith("/receipt")]
    assert result["status"] == "passed"
    assert result["checks"]["job_receipt_wrong_scope"] == 403
    assert result["checks"]["job_receipt_unsigned"] == 200
    assert result["audit_export_immutable"] is True
    assert result["checks"]["audit_export_write"] == 200
    assert result["audit_export_write_manifest_hash_present"] is True
    assert result["audit_export_write_event_count"] == 2
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
    assert result["checks"]["metrics"] == 200
    assert result["checks"]["alerts"] == 200
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
