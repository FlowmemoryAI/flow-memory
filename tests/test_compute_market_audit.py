from __future__ import annotations

import json
from typing import Any

from flow_memory.api.http_server import HttpApiConfig, HttpApiGateway
from flow_memory.compute_market.config import ComputeMarketConfig
from flow_memory.compute_market.service import ComputeMarketService, reset_default_service
from flow_memory.compute_market.storage import ComputeMarketStore
from flow_memory.cli import main as cli_main


def _service() -> ComputeMarketService:
    return ComputeMarketService(store=ComputeMarketStore(":memory:"), config=ComputeMarketConfig(database_url=":memory:", compute_market_mode="test"))


def test_audit_event_hash_created_and_chain_verifies() -> None:
    service = _service()
    service.plan({"task": "audit chain", "request_id": "audit-req"})

    events = service.audit({})["audit_events"]
    assert events
    assert all(event["event_hash"] for event in events)
    assert all(event["canonical_payload_hash"] for event in events)
    assert service.audit_verify({})["ok"] is True


def test_modified_audit_event_fails_verification() -> None:
    service = _service()
    service.plan({"task": "tamper action"})
    event = dict(service.audit({})["audit_events"][0])
    event["action"] = "compute.audit.tampered"
    service.store.put_record("audit_event", event["audit_event_id"], event, action=event["action"])

    result = service.store.verify_audit_chain()
    assert result.ok is False
    assert result.error_code == "audit_payload_hash_mismatch"
    readiness = service.readiness()
    assert readiness["ok"] is False
    assert "audit_chain_invalid" in readiness["readiness_failures"]


def test_missing_audit_event_fails_verification() -> None:
    service = _service()
    for index in range(3):
        service.plan({"task": f"missing audit {index}", "request_id": f"audit-{index}"})
    events = service.audit({})["audit_events"]
    middle = events[1]
    service.store.delete_record("audit_event", middle["audit_event_id"])

    result = service.store.verify_audit_chain()
    assert result.ok is False
    assert result.error_code == "audit_sequence_gap"


def test_wrong_previous_hash_fails_verification_and_chain_can_continue_after_valid_append() -> None:
    service = _service()
    service.plan({"task": "first"})
    service.plan({"task": "second"})
    event = dict(service.audit({})["audit_events"][1])
    event["previous_hash"] = "bad-previous-hash"
    service.store.put_record("audit_event", event["audit_event_id"], event, action=event["action"])

    broken = service.store.verify_audit_chain()
    assert broken.ok is False
    assert broken.error_code == "audit_previous_hash_mismatch"

    fresh = _service()
    fresh.plan({"task": "first valid append"})
    fresh.plan({"task": "second valid append"})
    assert fresh.store.verify_audit_chain().ok is True


def test_audit_verify_api_and_cli_work(capsys: Any) -> None:
    service = _service()
    service.plan({"task": "api verify"})
    reset_default_service(service)
    gateway = HttpApiGateway(config=HttpApiConfig(api_key="dev", require_scopes=True, enable_rate_limit=False))

    api = gateway.handle("GET", "/compute/audit/verify", {"x-flow-memory-api-key": "dev", "x-flow-memory-scopes": "compute:audit"})
    assert api.status == 200
    assert json.loads(api.to_bytes())["data"]["ok"] is True

    code = cli_main(["compute", "audit", "verify", "--json"])
    output = json.loads(capsys.readouterr().out)
    assert code == 0
    assert output["ok"] is True
    assert output["audit_chain"]["ok"] is True

def test_audit_export_checkpoint_and_verify_export_cli(capsys: Any, tmp_path: Any) -> None:
    service = _service()
    service.plan({"task": "export audit", "request_id": "req-export", "idempotency_key": "export-1"})
    reset_default_service(service)
    out = tmp_path / "audit_export.ndjson"

    exit_code = cli_main(["compute", "audit", "export", "--out", str(out), "--json"])
    exported = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert exported["ok"] is True
    assert out.exists()
    assert exported["checkpoint"]["checkpoint_hash"]

    exit_code = cli_main(["compute", "audit", "verify-export", "--path", str(out), "--json"])
    verified = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert verified["ok"] is True
    assert verified["event_count"] >= 1

    checkpoint_exit = cli_main(["compute", "audit", "checkpoint", "--json"])
    checkpointed = json.loads(capsys.readouterr().out)

    assert checkpoint_exit == 0
    assert checkpointed["ok"] is True
    assert checkpointed["checkpoint"]["checkpoint_hash"]


def test_audit_verify_export_detects_tampering(capsys: Any, tmp_path: Any) -> None:
    service = _service()
    service.plan({"task": "tamper audit", "request_id": "req-tamper", "idempotency_key": "tamper-1"})
    reset_default_service(service)
    out = tmp_path / "audit_export.ndjson"
    assert cli_main(["compute", "audit", "export", "--out", str(out), "--json"]) == 0
    capsys.readouterr()
    text = out.read_text(encoding="utf-8")
    out.write_text(text.replace("compute.plan.requested", "compute.plan.modified"), encoding="utf-8")

    exit_code = cli_main(["compute", "audit", "verify-export", "--path", str(out), "--json"])
    verified = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert verified["ok"] is False


def test_audit_export_refuses_secret_payload(tmp_path: Any) -> None:
    service = _service()
    service.store.append_audit_event(
        {
            "audit_event_id": "secret-event",
            "action": "compute.test",
            "request_id": "req-secret",
            "actor_id": "local",
            "actor_type": "system",
            "result": "completed",
            "dry_run_only": True,
            "funds_moved": False,
            "broadcast_allowed": False,
            "private_key_required": False,
            "created_at": "2026-05-25T00:00:00Z",
            "details": {"private_key": "forbidden"},
        }
    )

    result = service.audit_export({"out": str(tmp_path / "secret.ndjson")})

    assert result["ok"] is False
    assert "audit_export_refused" in result["warnings"]
