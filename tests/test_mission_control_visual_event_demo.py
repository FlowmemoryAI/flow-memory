import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_mission_control_visual_event_demo_runs():
    completed = subprocess.run([sys.executable, "examples/mission_control_visual_event_demo.py"], cwd=ROOT, check=True, capture_output=True, text=True)
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert payload["agent_count"] == 4
    assert payload["event_count"] >= 6
