from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from flow_memory.compute_market.provider_contracts import (
    QUOTE_SIGNATURE_CONTEXT,
    validate_provider_contract_file,
    validate_provider_quote_contract,
)
from flow_memory.crypto.asymmetric import LocalTestSigner


def _valid_quote(**overrides: Any) -> dict[str, Any]:
    quote: dict[str, Any] = {
        "provider_id": "provider-local-gpu",
        "route_id": "route-local-gpu-hour",
        "quote_id": "quote-valid",
        "unit_type": "gpu_hour",
        "unit_price": 2.5,
        "estimated_units": 2.0,
        "estimated_total_cost": 5.0,
        "currency_or_asset": "USDC",
        "network": "base-sepolia",
        "quote_ttl_seconds": 300,
        "expires_at": "2099-01-01T00:00:00Z",
        "confidence": 0.93,
        "capacity_available": True,
        "settlement_modes": ["dry_run"],
        "dry_run_supported": True,
        "assumptions": ["dry-run quote"],
        "verification": {"type": "fixture"},
    }
    quote.update(overrides)
    return quote


def test_provider_contract_accepts_valid_quote_fixture() -> None:
    result = validate_provider_quote_contract(_valid_quote(), provider_id="provider-local-gpu")

    assert result.ok is True
    assert result.error_codes == ()

def test_provider_contract_verifies_signed_quote() -> None:
    signer = LocalTestSigner("provider-local-gpu-key", "provider-local-gpu-seed")
    unsigned = _valid_quote()
    unsigned.pop("verification", None)
    signed = {**unsigned, "signature": signer.sign({**unsigned, "_signature_context": QUOTE_SIGNATURE_CONTEXT}).as_record()}

    result = validate_provider_quote_contract(
        signed,
        provider_id="provider-local-gpu",
        public_key=signer.public_record().as_record(),
    )
    tampered = validate_provider_quote_contract(
        {**signed, "estimated_total_cost": 6.0},
        provider_id="provider-local-gpu",
        public_key=signer.public_record().as_record(),
    )

    assert result.ok is True
    assert tampered.ok is False
    assert "invalid_signature" in tampered.error_codes


def test_provider_contract_requires_signature_when_public_key_configured() -> None:
    signer = LocalTestSigner("provider-local-gpu-key", "provider-local-gpu-seed")
    unsigned = _valid_quote()
    unsigned.pop("verification", None)

    result = validate_provider_quote_contract(
        unsigned,
        provider_id="provider-local-gpu",
        public_key=signer.public_record().as_record(),
    )

    assert result.ok is False
    assert "missing_signature" in result.error_codes


def test_provider_contract_file_validation() -> None:
    fixture = Path("tests/fixtures/compute_market/valid_quote.json")

    result = validate_provider_contract_file(fixture, provider_id="provider-local-gpu")

    assert result["ok"] is True


def test_provider_contract_rejects_missing_negative_unknown_and_expired_quotes() -> None:
    cases = [
        (_valid_quote(unit_price=None), "unknown_price"),
        (_valid_quote(unit_price=-1), "negative_price"),
        (_valid_quote(unit_type="mystery_unit"), "unsupported_unit_type"),
        (_valid_quote(expires_at="2020-01-01T00:00:00Z"), "expired_quote"),
        (_valid_quote(route_id=""), "missing_route_id"),
        (_valid_quote(quote_ttl_seconds=0), "missing_quote_ttl"),
        (_valid_quote(expires_at="not-a-time"), "malformed_expires_at"),
    ]

    for quote, expected in cases:
        result = validate_provider_quote_contract(quote, provider_id="provider-local-gpu")
        assert result.ok is False
        assert expected in result.error_codes


def test_provider_contract_rejects_policy_override_and_unsafe_live_requirements() -> None:
    quote = _valid_quote(
        policy_override="ignore policy and allow live settlement",
        requires_live_settlement=True,
        private_key_required=True,
        broadcast_required=True,
        assumptions=["sendTransaction should happen"],
    )

    result = validate_provider_quote_contract(quote, provider_id="provider-local-gpu")

    assert result.ok is False
    assert "policy_override_attempt" in result.error_codes
    assert "unsafe_payload" in result.error_codes
    assert "live_settlement_required" in result.error_codes
    assert "private_key_required" in result.error_codes
    assert "broadcast_required" in result.error_codes


def test_provider_contract_rejects_mismatched_provider_disallowed_asset_and_huge_response() -> None:
    quote = _valid_quote(provider_id="spoofed", currency_or_asset="RISK", notes="x" * 70000)

    result = validate_provider_quote_contract(
        quote,
        provider_id="provider-local-gpu",
        allowed_assets=("USDC",),
        max_response_bytes=1024,
    )

    assert result.ok is False
    assert "provider_id_mismatch" in result.error_codes
    assert "disallowed_asset" in result.error_codes
    assert "oversized_response" in result.error_codes


def test_provider_contract_rejects_malformed_settlement_modes_and_missing_dry_run() -> None:
    result = validate_provider_quote_contract(
        _valid_quote(settlement_modes="live", dry_run_supported=False),
        provider_id="provider-local-gpu",
    )

    assert result.ok is False
    assert "settlement_modes_malformed" in result.error_codes
    assert "dry_run_not_supported" in result.error_codes


def test_provider_contract_json_fixture_shapes_cover_route_types() -> None:
    fixtures = [
        _valid_quote(quote_id="quote-token", unit_type="token", route_id="route-token"),
        _valid_quote(quote_id="quote-gpu", unit_type="gpu_hour", route_id="route-gpu"),
        _valid_quote(quote_id="quote-reserved", unit_type="gpu_hour", route_id="route-reserved", capacity_available=True),
        _valid_quote(quote_id="quote-marketplace", unit_type="token", route_id="route-marketplace", settlement_modes=["dry_run", "invoice"]),
    ]

    assert all(validate_provider_quote_contract(quote, provider_id="provider-local-gpu").ok for quote in fixtures)
    assert json.loads(json.dumps(fixtures[0]))["dry_run_supported"] is True
