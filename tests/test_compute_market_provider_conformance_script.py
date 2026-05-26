from __future__ import annotations

import json
import os
from typing import Any

import scripts.validate_compute_market_provider_conformance as validator


def test_provider_sandbox_validator_ingests_and_selects_live_quote(monkeypatch: Any) -> None:
    monkeypatch.setenv(validator._SIGNING_SECRET_ENV, "existing-secret")

    result = validator.validate_provider_sandbox()

    assert result["ok"] is True
    assert result["provider_created"] is True
    assert result["route_created"] is True
    assert result["contract_ok"] is True
    assert result["quote_ingested"] is True
    assert result["provider_health_checked"] is True
    assert result["sandbox_health_status"] == 200
    assert result["quote_count"] == 1
    assert result["quote_cache_count"] == 1
    assert result["audit_ingested"] is True
    assert result["health_count"] >= 1
    assert result["selected_route_id"] == validator._ROUTE_ID
    assert result["selected_quote_source"] == "live_provider"
    assert result["fail_closed_errors"] == ()
    assert result["dry_run_only"] is True
    assert result["funds_moved"] is False
    assert result["broadcast_allowed"] is False
    assert result["private_key_required"] is False
    assert os.environ[validator._SIGNING_SECRET_ENV] == "existing-secret"


def test_provider_sandbox_validator_main_outputs_json(capsys: Any) -> None:
    exit_code = validator.main([])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["selected_route_id"] == validator._ROUTE_ID
    assert payload["selected_quote_source"] == "live_provider"
