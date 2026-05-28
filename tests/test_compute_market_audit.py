from __future__ import annotations

import json
from datetime import timedelta
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
        self.heads: dict[tuple[str, str], dict[str, Any]] = {}

    def put_object(self, **kwargs: Any) -> dict[str, Any]:
        bucket = str(kwargs["Bucket"])
        key = str(kwargs["Key"])
        body = kwargs.get("Body", b"")
        body_bytes = body if isinstance(body, bytes) else str(body).encode("utf-8")
        self.objects[(bucket, key)] = body_bytes
        self.heads[(bucket, key)] = {
            "ContentLength": len(body_bytes),
            "Metadata": dict(kwargs.get("Metadata", {})),
            "ObjectLockMode": kwargs.get("ObjectLockMode", ""),
            "ObjectLockRetainUntilDate": kwargs.get("ObjectLockRetainUntilDate"),
        }
        self.puts.append(dict(kwargs))
        return {"ETag": "fake-etag"}

    def head_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        if (Bucket, Key) not in self.objects:
            raise KeyError(Key)
        return dict(self.heads[(Bucket, Key)])

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
    try:
        service.store.put_record("audit_event", event["audit_event_id"], event, action=event["action"])
    except ValueError as exc:
        assert "append-only" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("audit event overwrite was accepted without force")
    service.store.put_record(
        "audit_event",
        event["audit_event_id"],
        event,
        action=event["action"],
        _allow_audit_event_mutation=True,
    )

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
    try:
        service.store.delete_record("audit_event", middle["audit_event_id"])
    except ValueError as exc:
        assert "append-only" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("audit event deletion was accepted without force")
    service.store.delete_record("audit_event", middle["audit_event_id"], _allow_audit_event_mutation=True)

    result = service.store.verify_audit_chain()
    assert result.ok is False
    assert result.error_code == "audit_sequence_gap"


def test_wrong_previous_hash_fails_verification_and_chain_can_continue_after_valid_append() -> None:
    service = _service()
    service.plan({"task": "first"})
    service.plan({"task": "second"})
    event = dict(service.audit({})["audit_events"][1])
    event["previous_hash"] = "bad-previous-hash"
    service.store.put_record(
        "audit_event",
        event["audit_event_id"],
        event,
        action=event["action"],
        _allow_audit_event_mutation=True,
    )

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


def test_audit_verify_export_detects_manifest_tampering(capsys: Any, tmp_path: Any) -> None:
    service = _service()
    service.plan({"task": "tamper audit manifest", "request_id": "req-manifest-tamper", "idempotency_key": "manifest-tamper-1"})
    reset_default_service(service)
    out = tmp_path / "audit_export.ndjson"
    assert cli_main(["compute", "audit", "export", "--out", str(out), "--json"]) == 0
    capsys.readouterr()

    lines = out.read_text(encoding="utf-8").splitlines()
    manifest = json.loads(lines[0])
    manifest["created_at"] = "2099-01-01T00:00:00Z"
    lines[0] = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    verified = LocalFileAuditExporter(out).verify_export()

    assert verified.ok is False
    assert verified.error_code == "manifest_hash_mismatch"


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
        config=ComputeMarketConfig(
            database_url=":memory:",
            compute_market_mode="test",
            audit_export_required=True,
            audit_export_uri="s3://flow-memory-audit/compute-market",
            audit_export_immutable_required=True,
            audit_export_object_lock_mode="COMPLIANCE",
            audit_export_retention_days=30,
            audit_export_s3_region="us-east-1",
        ),
        audit_exporter=exporter,
    )
    service.plan({"task": "s3 object lock export", "request_id": "s3-worm"})

    exported = service.audit_export({"chain_id": "all"})
    verified = exporter.verify_export()
    readiness = service.readiness()

    assert exported["ok"] is True
    assert exported["path"].startswith("s3://flow-memory-audit/compute-market/exports/")
    assert exported["checkpoint"]["exported_to"] == "s3_object_lock"
    assert exported["checkpoint"]["object_lock_mode"] == "COMPLIANCE"
    assert exported["checkpoint"]["retention_until"]
    assert verified.ok is True
    assert readiness["ready"] is True
    assert readiness["audit_exporter_status"]["immutable"] is True
    assert len(client.puts) == 2
    assert {put["ContentType"] for put in client.puts} == {"application/x-ndjson", "application/json"}
    assert all(put["ObjectLockMode"] == "COMPLIANCE" for put in client.puts)
    assert all(put["ObjectLockRetainUntilDate"] for put in client.puts)
    export_put = next(put for put in client.puts if put["ContentType"] == "application/x-ndjson")
    export_bucket = str(export_put["Bucket"])
    export_key = str(export_put["Key"])
    export_body = client.objects[(export_bucket, export_key)]
    assert client.heads[(export_bucket, export_key)]["Metadata"]["manifest-hash"] == exported["manifest_hash"]
    assert client.heads[(export_bucket, export_key)]["ObjectLockMode"] == "COMPLIANCE"
    assert client.heads[(export_bucket, export_key)]["ObjectLockRetainUntilDate"]
    manifest = json.loads(export_body.decode("utf-8").splitlines()[0])
    assert manifest["object_lock_mode"] == "COMPLIANCE"
    assert manifest["storage_uri"] == exported["path"]
    assert manifest["retention_until"]
    checkpoint_put = next(put for put in client.puts if put["ContentType"] == "application/json")
    checkpoint_bucket = str(checkpoint_put["Bucket"])
    checkpoint_key = str(checkpoint_put["Key"])
    checkpoint_record = json.loads(client.objects[(checkpoint_bucket, checkpoint_key)].decode("utf-8"))
    assert checkpoint_record["retention_until"] == exported["checkpoint"]["retention_until"]
    assert checkpoint_put["ObjectLockRetainUntilDate"].replace(microsecond=0).isoformat().replace("+00:00", "Z") == exported["checkpoint"]["retention_until"]
    lines = export_body.decode("utf-8").splitlines()
    manifest["created_at"] = "2099-01-01T00:00:00Z"
    lines[0] = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    client.objects[(export_bucket, export_key)] = ("\n".join(lines) + "\n").encode("utf-8")
    tampered = exporter.verify_export()
    assert tampered.ok is False
    assert tampered.error_code == "manifest_hash_mismatch"

def test_s3_object_lock_readback_rejects_wrong_retention_date() -> None:
    class TruncatingRetentionClient(FakeS3Client):
        def put_object(self, **kwargs: Any) -> dict[str, Any]:
            result = super().put_object(**kwargs)
            bucket = str(kwargs["Bucket"])
            key = str(kwargs["Key"])
            self.heads[(bucket, key)]["ObjectLockRetainUntilDate"] = kwargs["ObjectLockRetainUntilDate"] - timedelta(days=1)
            return result

    client = TruncatingRetentionClient()
    exporter = S3WormAuditExporter("flow-memory-audit", "compute-market", retention_days=30, client=client)
    service = _service()
    service.plan({"task": "truncated retention export", "request_id": "s3-retention-truncated-write"})

    try:
        exporter.export_events(service.store, chain_id="all")
    except RuntimeError as exc:
        assert "retention timestamp mismatch" in str(exc)
    else:
        raise AssertionError("S3 Object Lock exporter accepted a truncated retention timestamp")


def test_s3_object_lock_checkpoint_readback_rejects_corrupt_body() -> None:
    class CorruptCheckpointBodyClient(FakeS3Client):
        def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
            if "/checkpoints/" in Key:
                return {"Body": b'{"checkpoint_id":"corrupt"}'}
            return super().get_object(Bucket=Bucket, Key=Key)

    client = CorruptCheckpointBodyClient()
    exporter = S3WormAuditExporter("flow-memory-audit", "compute-market", retention_days=30, client=client)
    service = _service()
    service.plan({"task": "corrupt checkpoint body", "request_id": "s3-corrupt-checkpoint-body"})
    exported = exporter.export_events(service.store, chain_id="all")

    try:
        exporter.write_checkpoint(exported.checkpoint)
    except RuntimeError as exc:
        assert "checkpoint body readback mismatch" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("S3 exporter accepted a corrupted checkpoint body readback")


def test_s3_object_lock_verify_export_detects_retention_truncation() -> None:
    client = FakeS3Client()
    exporter = S3WormAuditExporter("flow-memory-audit", "compute-market", retention_days=30, client=client)
    service = _service()
    service.plan({"task": "verify truncated retention", "request_id": "s3-retention-truncated-verify"})

    exported = exporter.export_events(service.store, chain_id="all")
    export_key = exported.path.removeprefix("s3://flow-memory-audit/")
    head = client.heads[("flow-memory-audit", export_key)]
    head["ObjectLockRetainUntilDate"] = head["ObjectLockRetainUntilDate"] - timedelta(days=1)

    verified = exporter.verify_export()

    assert verified.ok is False
    assert verified.error_code == "RuntimeError"
    assert "retention timestamp mismatch" in verified.message


def test_s3_object_lock_exporter_signs_manifest_and_checkpoint(monkeypatch: Any) -> None:
    monkeypatch.setenv("FLOW_MEMORY_AUDIT_SIGNING_SECRET", "audit-signing-secret")
    client = FakeS3Client()
    exporter = S3WormAuditExporter(
        "flow-memory-audit",
        "compute-market",
        retention_days=30,
        client=client,
        manifest_signing_key_id="audit-key-1",
        manifest_signing_secret_env="FLOW_MEMORY_AUDIT_SIGNING_SECRET",
    )
    service = _service()
    service.plan({"task": "s3 signed object lock export", "request_id": "s3-signed-worm"})

    exported = exporter.export_events(service.store, chain_id="all")
    checkpoint_written = exporter.write_checkpoint(exported.checkpoint)
    verified = exporter.verify_export()

    assert verified.ok is True
    export_put = next(put for put in client.puts if put["ContentType"] == "application/x-ndjson")
    export_bucket = str(export_put["Bucket"])
    export_key = str(export_put["Key"])
    export_lines = client.objects[(export_bucket, export_key)].decode("utf-8").splitlines()
    manifest = json.loads(export_lines[0])
    assert manifest["manifest_signature"]["key_id"] == "audit-key-1"
    assert client.heads[(export_bucket, export_key)]["Metadata"]["manifest-signature-key-id"] == "audit-key-1"

    checkpoint_put = next(put for put in client.puts if put["ContentType"] == "application/json")
    checkpoint_bucket = str(checkpoint_put["Bucket"])
    checkpoint_key = str(checkpoint_put["Key"])
    checkpoint_record = json.loads(client.objects[(checkpoint_bucket, checkpoint_key)].decode("utf-8"))
    assert checkpoint_record["checkpoint_signature"]["key_id"] == "audit-key-1"
    assert checkpoint_written["checkpoint_record"]["checkpoint_signature"]["key_id"] == "audit-key-1"
    assert client.heads[(checkpoint_bucket, checkpoint_key)]["Metadata"]["checkpoint-signature-key-id"] == "audit-key-1"

    manifest["manifest_signature"] = {**manifest["manifest_signature"], "signature": "bad-signature"}
    export_lines[0] = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    client.objects[(export_bucket, export_key)] = ("\n".join(export_lines) + "\n").encode("utf-8")
    tampered = exporter.verify_export()

    assert tampered.ok is False
    assert tampered.error_code == "manifest_signature_mismatch"


def test_s3_object_lock_exporter_fails_closed_when_manifest_signing_secret_missing(monkeypatch: Any) -> None:
    monkeypatch.delenv("FLOW_MEMORY_MISSING_AUDIT_SIGNING_SECRET", raising=False)
    exporter = S3WormAuditExporter(
        "flow-memory-audit",
        "compute-market",
        retention_days=30,
        client=FakeS3Client(),
        manifest_signing_key_id="audit-key-1",
        manifest_signing_secret_env="FLOW_MEMORY_MISSING_AUDIT_SIGNING_SECRET",
    )
    service = _service()
    service.plan({"task": "s3 missing signing secret", "request_id": "s3-missing-signing-secret"})

    try:
        exporter.export_events(service.store, chain_id="all")
    except RuntimeError as exc:
        assert "signing secret env" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("S3 exporter wrote a signed manifest without a signing secret")


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


def test_s3_object_lock_exporter_fails_closed_without_head_readback_retention() -> None:
    class MissingRetentionS3Client(FakeS3Client):
        def head_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
            response = super().head_object(Bucket=Bucket, Key=Key)
            response.pop("ObjectLockRetainUntilDate", None)
            return response

    client = MissingRetentionS3Client()
    exporter = S3WormAuditExporter("flow-memory-audit", "compute-market", retention_days=30, client=client)
    service = _service()
    service.plan({"task": "s3 missing retention readback", "request_id": "s3-no-retention"})

    try:
        exporter.export_events(service.store, chain_id="all")
    except RuntimeError as exc:
        assert "readback retention timestamp" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("S3 exporter accepted missing readback retention evidence")


def test_s3_object_lock_verify_export_fails_closed_without_retention_readback() -> None:
    client = FakeS3Client()
    exporter = S3WormAuditExporter("flow-memory-audit", "compute-market", retention_days=30, client=client)
    service = _service()
    service.plan({"task": "s3 verify missing retention readback", "request_id": "s3-verify-no-retention"})

    exporter.export_events(service.store, chain_id="all")
    export_put = client.puts[0]
    export_key = str(export_put["Key"])
    client.heads[(str(export_put["Bucket"]), export_key)].pop("ObjectLockRetainUntilDate", None)
    verified = exporter.verify_export()

    assert verified.ok is False
    assert verified.error_code == "RuntimeError"
    assert "readback retention timestamp" in verified.message


def test_s3_exporter_factory_uses_first_class_region_endpoint_and_retention_config() -> None:
    exporter = create_audit_exporter(
        "s3://flow-memory-audit/compute-market?retention_days=7&signing_key_id=audit-key-1&signing_secret_env=FLOW_MEMORY_AUDIT_SIGNING_SECRET",
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
    assert exporter.manifest_signing_key_id == "audit-key-1"
    assert exporter.manifest_signing_secret_env == "FLOW_MEMORY_AUDIT_SIGNING_SECRET"


def test_audit_checkpoint_writes_configured_local_exporter_checkpoint(tmp_path: Any) -> None:
    out = tmp_path / "configured" / "audit.ndjson"
    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(database_url=":memory:", compute_market_mode="test", audit_export_uri=str(out), audit_export_required=True),
    )
    service.plan({"task": "configured checkpoint write", "request_id": "checkpoint-local-write"})

    result = service.audit_checkpoint({"chain_id": "all"})
    checkpoint_path = out.with_suffix(out.suffix + ".checkpoint.json")
    written = json.loads(checkpoint_path.read_text(encoding="utf-8"))

    assert checkpoint_path.exists()
    assert written["checkpoint_id"] == result["checkpoint"]["checkpoint_id"]
    assert result["checkpoint"]["exported_to"] == "local_file_checkpoint"
    assert result["checkpoint_record"]["storage_uri"] == str(checkpoint_path)
    assert result["checkpoint_record"]["checkpoint_write"]["ok"] is True
    assert result["checkpoint_record"]["checkpoint_write"]["path"] == str(checkpoint_path)


def test_audit_checkpoint_writes_immutable_s3_checkpoint_when_required() -> None:
    client = FakeS3Client()
    exporter = S3WormAuditExporter("flow-memory-audit", "compute-market", retention_days=30, client=client)
    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(
            database_url=":memory:",
            compute_market_mode="test",
            audit_export_required=True,
            audit_export_uri="s3://flow-memory-audit/compute-market",
            audit_export_immutable_required=True,
            audit_export_object_lock_mode="COMPLIANCE",
            audit_export_retention_days=30,
            audit_export_s3_region="us-east-1",
        ),
        audit_exporter=exporter,
    )
    service.plan({"task": "immutable checkpoint write", "request_id": "checkpoint-s3-write"})

    result = service.audit_checkpoint({"chain_id": "all"})
    put = client.puts[0]
    checkpoint_bucket = str(put["Bucket"])
    checkpoint_key = str(put["Key"])
    checkpoint_record = json.loads(client.objects[(checkpoint_bucket, checkpoint_key)].decode("utf-8"))

    assert result["checkpoint"]["exported_to"] == "s3_object_lock_checkpoint"
    assert len(client.puts) == 1
    assert put["ContentType"] == "application/json"
    assert put["ObjectLockMode"] == "COMPLIANCE"
    assert put["ObjectLockRetainUntilDate"]
    assert result["checkpoint_record"]["storage_uri"].startswith("s3://flow-memory-audit/compute-market/checkpoints/")
    assert result["checkpoint_record"]["object_lock_mode"] == "COMPLIANCE"
    assert result["checkpoint_record"]["retention_until"]
    assert checkpoint_record["storage_uri"] == result["checkpoint_record"]["storage_uri"]
    assert checkpoint_record["object_lock_mode"] == "COMPLIANCE"
    assert checkpoint_record["retention_until"] == result["checkpoint_record"]["retention_until"]


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
    stale_monitor = service.audit_chain_monitor({})
    stale_metric_total = service.telemetry.summary()["metric_totals"].get("audit_checkpoint_stale_total", 0.0)
    interval_scheduled = service.audit_checkpoint_schedule({"chain_id": "all", "min_events": 100, "interval_seconds": 1})
    assert interval_scheduled["interval_due"] is True
    assert interval_scheduled["due"] is True
    assert stale_monitor["checkpoint_stale"] is True
    assert stale_monitor["stale_checkpoint_warning"]
    assert stale_metric_total == 1.0


def test_audit_checkpoint_schedule_initial_interval_uses_oldest_pending_event() -> None:
    service = _service()
    service.plan({"task": "initial interval checkpoint", "request_id": "initial-checkpoint-interval"})
    event = dict(service.store.list_records("audit_event", limit=1).records[0])
    event["created_at"] = "2000-01-01T00:00:00Z"
    service.store.put_record(
        "audit_event",
        event["audit_event_id"],
        event,
        action=event["action"],
        _allow_audit_event_mutation=True,
    )

    scheduled = service.audit_checkpoint_schedule({"chain_id": "all", "min_events": 100, "interval_seconds": 1})

    assert scheduled["interval_due"] is True
    assert scheduled["due"] is True
    assert scheduled["pending_event_count"] >= 1
    assert scheduled["scheduled_result"]["checkpoint_record"]["checkpoint_id"]


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

def test_audit_replay_checkpoint_schedule_and_monitor_cli(capsys: Any) -> None:
    service = _service()
    service.plan({"task": "cli audit operations", "request_id": "cli-audit-ops"})
    reset_default_service(service)
    try:
        replay_exit = cli_main(["compute", "audit", "replay", "--json"])
        replay = json.loads(capsys.readouterr().out)

        schedule_exit = cli_main(["compute", "audit", "checkpoint-schedule", "--force", "--min-events", "1", "--json"])
        scheduled = json.loads(capsys.readouterr().out)

        monitor_exit = cli_main(["compute", "audit", "chain-monitor", "--json"])
        monitor = json.loads(capsys.readouterr().out)
    finally:
        reset_default_service(None)

    assert replay_exit == 0
    assert replay["ok"] is True
    assert replay["replay"]["source"] == "store"
    assert replay["replay"]["timeline"]
    assert service.store.count_records("audit_replay_run") == 1

    assert schedule_exit == 0
    assert scheduled["due"] is True
    assert scheduled["scheduled_result"]["ok"] is True
    assert scheduled["scheduled_result"]["checkpoint"]["checkpoint_hash"]
    assert service.store.count_records("audit_checkpoint_manifest") == 1

    assert monitor_exit == 0
    assert monitor["ok"] is True
    assert monitor["checkpoint_count"] == 1
    assert monitor["chains"]


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
