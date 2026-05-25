from __future__ import annotations

import json
from typing import Any

from flow_memory.api.http_server import HttpApiConfig, HttpApiGateway
from flow_memory.compute_market.config import ComputeMarketConfig
from flow_memory.compute_market.service import ComputeMarketService, reset_default_service
from flow_memory.compute_market.storage import ComputeMarketStore
from flow_memory.compute_market.audit_export import LocalFileAuditExporter, NoopAuditExporter, S3WormAuditExporter, create_audit_exporter
from flow_memory.cli import main as cli_main


def _service() -> ComputeMarketService:
    return ComputeMarketService(store=ComputeMarketStore(":memory:"), config=ComputeMarketConfig(database_url=":memory:", compute_market_mode="test"))


class FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.puts: list[dict[str, Any]] = []

    def put_object(self, **kwargs: Any) -> dict[str, Any]:
        bucket = str(kwargs["Bucket"])
        key = str(kwargs["Key"])
        body = kwargs.get("Body", b"")
        self.objects[(bucket, key)] = body if isinstance(body, bytes) else str(body).encode("utf-8")
        self.puts.append(dict(kwargs))
        return {"ETag": "fake-etag"}

    def head_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        if (Bucket, Key) not in self.objects:
            raise KeyError(Key)
        return {"ContentLength": len(self.objects[(Bucket, Key)])}

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        return {"Body": self.objects[(Bucket, Key)]}

    def get_bucket_object_lock_configuration(self, *, Bucket: str) -> dict[str, Any]:
        return {"ObjectLockConfiguration": {"ObjectLockEnabled": "Enabled"}}


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
    middle = next(event for event in events if int(event.get("sequence_number", 0) or 0) == 2)
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


def test_audit_export_uses_configured_exporter_when_out_is_omitted(tmp_path: Any) -> None:
    out = tmp_path / "configured" / "audit.ndjson"
    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(database_url=":memory:", compute_market_mode="test", audit_export_uri=str(out), audit_export_required=True),
    )
    service.plan({"task": "configured audit export"})

    exported = service.audit_export({"chain_id": "all"})
    readiness = service.readiness()

    assert exported["ok"] is True
    assert exported["path"] == str(out)
    assert out.exists()
    assert readiness["ready"] is True
    assert readiness["audit_exporter_status"]["configured"] is True


def test_audit_exporter_factory_resolves_file_s3_and_empty(tmp_path: Any) -> None:
    local = create_audit_exporter(tmp_path / "audit.ndjson")
    file_uri = create_audit_exporter((tmp_path / "file-uri.ndjson").as_uri())
    s3 = create_audit_exporter("s3://flow-memory-audit/checkpoints")
    empty = create_audit_exporter("")

    assert isinstance(local, LocalFileAuditExporter)
    assert isinstance(file_uri, LocalFileAuditExporter)
    assert isinstance(s3, S3WormAuditExporter)
    assert isinstance(empty, NoopAuditExporter)
    assert s3.get_status()["exporter"] == "s3_object_lock"
    assert s3.get_status()["immutable"] is False


def test_s3_object_lock_exporter_writes_retained_export_checkpoint_and_verifies_readback() -> None:
    client = FakeS3Client()
    exporter = S3WormAuditExporter("flow-memory-audit", "compute-market", retention_days=30, client=client)
    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(database_url=":memory:", compute_market_mode="test", audit_export_required=True, audit_export_uri="s3://flow-memory-audit/compute-market"),
        audit_exporter=exporter,
    )
    service.plan({"task": "s3 object lock export", "request_id": "s3-worm"})

    exported = service.audit_export({"chain_id": "all"})
    verified = exporter.verify_export()

    assert exported["ok"] is True
    assert exported["path"].startswith("s3://flow-memory-audit/compute-market/exports/")
    assert exported["checkpoint"]["exported_to"] == "s3_object_lock"
    assert exported["checkpoint"]["object_lock_mode"] == "COMPLIANCE"
    assert exported["checkpoint"]["retention_until"]
    assert verified.ok is True
    assert len(client.puts) == 2
    assert {put["ContentType"] for put in client.puts} == {"application/x-ndjson", "application/json"}
    assert all(put["ObjectLockMode"] == "COMPLIANCE" for put in client.puts)
    assert all(put["ObjectLockRetainUntilDate"] for put in client.puts)
    export_body = next(client.objects[(str(put["Bucket"]), str(put["Key"]))] for put in client.puts if put["ContentType"] == "application/x-ndjson")
    manifest = json.loads(export_body.decode("utf-8").splitlines()[0])
    assert manifest["object_lock_mode"] == "COMPLIANCE"
    assert manifest["storage_uri"] == exported["path"]
    assert manifest["retention_until"]



def test_s3_object_lock_exporter_fails_closed_without_bucket_object_lock() -> None:
    class UnlockedS3Client(FakeS3Client):
        def get_bucket_object_lock_configuration(self, *, Bucket: str) -> dict[str, Any]:
            return {"ObjectLockConfiguration": {"ObjectLockEnabled": "Disabled"}}

    exporter = S3WormAuditExporter("flow-memory-audit", "compute-market", retention_days=30, client=UnlockedS3Client())
    service = ComputeMarketService(store=ComputeMarketStore(":memory:"), config=ComputeMarketConfig(database_url=":memory:", compute_market_mode="test"), audit_exporter=exporter)
    service.plan({"task": "s3 object lock disabled", "request_id": "s3-unlocked"})

    status = exporter.get_status()
    assert status["configured"] is False
    assert status["immutable"] is False

    try:
        service.audit_export({"chain_id": "all"})
    except ValueError as exc:
        assert "configured audit_export_uri" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("S3 service export accepted an unlocked bucket")
    try:
        exporter.export_events(service.store, chain_id="all")
    except RuntimeError as exc:
        assert "Object Lock" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("S3 exporter wrote without bucket Object Lock")


def test_s3_exporter_factory_uses_first_class_region_endpoint_and_retention_config() -> None:
    exporter = create_audit_exporter(
        "s3://flow-memory-audit/compute-market?retention_days=7",
        s3_region="us-east-1",
        s3_endpoint_url="https://s3.us-east-1.amazonaws.com",
        object_lock_mode="GOVERNANCE",
        retention_days=90,
    )

    assert isinstance(exporter, S3WormAuditExporter)
    assert exporter.region_name == "us-east-1"
    assert exporter.endpoint_url == "https://s3.us-east-1.amazonaws.com"
    assert exporter.object_lock_mode == "GOVERNANCE"
    assert exporter.retention_days == 90


def test_audit_checkpoint_schedule_monitor_and_admin_status(tmp_path: Any) -> None:
    out = tmp_path / "scheduled.ndjson"
    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(database_url=":memory:", compute_market_mode="test", audit_export_uri=str(out), audit_export_required=True),
    )
    service.plan({"task": "checkpoint schedule one", "request_id": "sched-1"})
    service.plan({"task": "checkpoint schedule two", "request_id": "sched-2"})

    skipped = service.audit_checkpoint_schedule({"chain_id": "all", "min_events": 100})
    scheduled = service.audit_checkpoint_schedule({"chain_id": "all", "min_events": 1, "force": True})
    monitor = service.audit_chain_monitor({})
    admin_status = service.admin_audit_export_status({})

    assert skipped["due"] is False
    assert scheduled["due"] is True
    assert scheduled["scheduled_result"]["checkpoint_record"]["checkpoint_id"]
    assert service.store.count_records("audit_checkpoint_manifest") == 1
    assert monitor["ok"] is True
    assert monitor["checkpoint_count"] == 1
    assert admin_status["ok"] is True
    assert admin_status["immutable"] is False
    assert admin_status["latest_checkpoint"]["checkpoint_id"] == scheduled["scheduled_result"]["checkpoint_record"]["checkpoint_id"]
    stale_checkpoint = dict(scheduled["scheduled_result"]["checkpoint_record"])
    stale_checkpoint["created_at"] = "2000-01-01T00:00:00Z"
    service.store.put_record(
        "audit_checkpoint_manifest",
        str(stale_checkpoint["checkpoint_id"]),
        stale_checkpoint,
    )
    interval_scheduled = service.audit_checkpoint_schedule({"chain_id": "all", "min_events": 100, "interval_seconds": 1})
    assert interval_scheduled["interval_due"] is True
    assert interval_scheduled["due"] is True


def test_audit_forensic_replay_from_store_and_export_file(tmp_path: Any) -> None:
    service = _service()
    service.plan({"task": "replay source", "request_id": "replay-1"})
    out = tmp_path / "replay.ndjson"
    exported = service.audit_export({"out": str(out), "chain_id": "all"})
    store_replay = service.audit_forensic_replay({"chain_id": "all"})
    file_replay = service.audit_forensic_replay({"path": str(out)})

    assert exported["ok"] is True
    assert store_replay["ok"] is True
    assert file_replay["ok"] is True
    assert store_replay["replay"]["timeline"]
    assert file_replay["replay"]["timeline"]
    assert file_replay["replay"]["source"] == "export_file"
    assert file_replay["replay"]["summary"]["event_count"] == file_replay["replay"]["event_count"]
    assert service.store.count_records("audit_replay_run") == 2


def test_audit_operations_are_exposed_through_http_gateway(tmp_path: Any) -> None:
    service = _service()
    service.plan({"task": "http audit ops", "request_id": "http-audit"})
    reset_default_service(service)
    gateway = HttpApiGateway(config=HttpApiConfig(api_key="dev", require_scopes=True, enable_rate_limit=False))
    headers = {"x-flow-memory-api-key": "dev", "x-flow-memory-scopes": "compute:audit compute:admin"}

    replay = gateway.handle("POST", "/compute/audit/replay", headers, b"{}")
    monitor = gateway.handle("GET", "/compute/audit/chain/monitor", headers)
    scheduled = gateway.handle("POST", "/compute/audit/checkpoint-schedule", headers, b'{"force":true}')
    admin = gateway.handle("GET", "/admin/audit/export", headers)

    assert replay.status == 200
    assert replay.body["data"]["ok"] is True
    assert monitor.status == 200
    assert monitor.body["data"]["ok"] is True
    assert scheduled.status == 200
    assert scheduled.body["data"]["due"] is True
    assert admin.status == 200
    assert "audit_exporter_status" in admin.body["data"]

def test_audit_checkpoint_paginates_all_events() -> None:
    service = _service()
    for index in range(520):
        service.store.append_audit_event(
            {
                "audit_event_id": f"manual-audit-{index}",
                "action": "compute.test",
                "request_id": f"req-{index}",
                "actor_id": "local",
                "actor_type": "system",
                "result": "completed",
                "dry_run_only": True,
                "funds_moved": False,
                "broadcast_allowed": False,
                "private_key_required": False,
                "created_at": f"2026-05-25T00:{index // 60:02d}:{index % 60:02d}Z",
            }
        )

    checkpoint = service.audit_checkpoint({"chain_id": "all"})["checkpoint"]

    assert checkpoint["event_count"] == 520
    assert checkpoint["to_sequence"] == 520
