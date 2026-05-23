from flow_memory.safety import ImmutableAuditLog


def test_audit_log_verifies_persisted_file(tmp_path) -> None:
    log = ImmutableAuditLog(path=tmp_path / "audit.jsonl")
    log.append({"kind": "test", "value": 1})
    log.append({"kind": "test", "value": 2})
    assert log.verify()
    assert log.verify_file()
