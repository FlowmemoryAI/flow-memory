import json
import subprocess
import sys
from pathlib import Path

from scripts.validate_visual_replay import validate_visual_replay

ROOT = Path(__file__).resolve().parents[1]


def test_validate_visual_replay_accepts_committed_replay() -> None:
    result = validate_visual_replay(ROOT / "dashboard" / "src" / "mock-data" / "local-network-replay.json")

    assert result["ok"] is True
    assert result["agent_count"] >= 1
    assert result["task_count"] >= 1
    assert result["economy_edge_count"] >= 1


def test_validate_visual_replay_rejects_missing_file(tmp_path: Path) -> None:
    result = validate_visual_replay(tmp_path / "missing.json")

    assert result["ok"] is False
    assert "visual_replay_missing" in result["blockers"]


def test_validate_visual_replay_script_outputs_json(tmp_path: Path) -> None:
    source = ROOT / "dashboard" / "src" / "mock-data" / "local-network-replay.json"
    target = tmp_path / "replay.json"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, "scripts/validate_visual_replay.py", str(target)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True


def test_validate_visual_replay_rejects_incomplete_replay(tmp_path: Path) -> None:
    replay = tmp_path / "bad.json"
    replay.write_text(json.dumps({"ok": True, "schema_version": "visual.telemetry.v1", "provenance": "replay", "events": [], "state": {}}), encoding="utf-8")

    result = validate_visual_replay(replay)

    assert result["ok"] is False
    assert "visual_replay_events_missing" in result["blockers"]
    assert "visual_replay_agents_missing" in result["blockers"]
