# Audit Replay

Flow Memory can export local chained audit events to JSONL, replay them, and detect tampering.

Commands:

```bash
python scripts/export_event_log.py
python scripts/replay_event_log.py
python scripts/verify_storage_integrity.py
```

The implementation is local/offline evidence tooling. It is not an external timestamping service or blockchain anchor.
