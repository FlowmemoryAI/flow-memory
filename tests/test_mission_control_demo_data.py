import json
import subprocess
import sys
from pathlib import Path

from scripts.mission_control_demo_data import generate_demo_data

ROOT = Path(__file__).resolve().parents[1]


def test_generate_mission_control_demo_data(tmp_path):
    payload = generate_demo_data(report_out=tmp_path / "report.json", replay_out=tmp_path / "replay.json")
    assert payload["ok"] is True
    assert payload["agent_count"] == 4
    assert payload["event_count"] >= 6


def test_mission_control_demo_data_script(tmp_path):
    completed = subprocess.run(
        [sys.executable, "scripts/mission_control_demo_data.py", "--report-out", str(tmp_path / "report.json"), "--replay-out", str(tmp_path / "replay.json")],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert Path(payload["replay_path"]).exists()
