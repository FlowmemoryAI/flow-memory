import json
import subprocess
import sys
from pathlib import Path

from scripts.export_visual_replay import export_visual_replay
from flow_memory.network import LocalNetworkOrchestrator

ROOT = Path(__file__).resolve().parents[1]


def test_export_visual_replay_from_network_report(tmp_path):
    report_path = tmp_path / "network.json"
    replay_path = tmp_path / "replay.json"
    report = LocalNetworkOrchestrator().run("all", emit_visual_events=True).as_record()
    report_path.write_text(json.dumps(report, default=str), encoding="utf-8")
    replay = export_visual_replay(report_path, replay_path)
    assert replay["ok"] is True
    assert replay["metadata"]["agent_count"] == 4
    assert replay_path.exists()


def test_export_visual_replay_script(tmp_path):
    report_path = tmp_path / "network.json"
    replay_path = tmp_path / "replay.json"
    report = LocalNetworkOrchestrator().run("all", emit_visual_events=True).as_record()
    report_path.write_text(json.dumps(report, default=str), encoding="utf-8")
    completed = subprocess.run([sys.executable, "scripts/export_visual_replay.py", str(report_path), "--out", str(replay_path)], cwd=ROOT, check=True, capture_output=True, text=True)
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert replay_path.exists()
