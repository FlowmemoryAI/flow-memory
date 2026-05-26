from __future__ import annotations

import json
from pathlib import Path

from flow_memory.visualization import build_visual_snapshot, visual_event
from flow_memory.visualization.snapshots import write_visual_snapshot


def test_visual_snapshot_writes_json(tmp_path: Path) -> None:
    events = (visual_event("agent", "did:flow:a", {"agent_id": "did:flow:a", "label": "A"}),)
    out = tmp_path / "snapshot.json"
    snapshot = write_visual_snapshot(events, out)
    assert snapshot["ok"] is True
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["state"]["agents"][0]["agent_id"] == "did:flow:a"


def test_build_visual_snapshot_labels_provenance() -> None:
    snapshot = build_visual_snapshot((visual_event("memory", "memory", {"memory_id": "m1", "summary": "remember"}),), provenance="replay")
    assert snapshot["state"]["provenance"] == "replay"
