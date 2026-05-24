import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_launch_agent_api_demo_runs_through_local_gateway():
    completed = subprocess.run([sys.executable, "examples/launch_agent_api_demo.py"], cwd=ROOT, check=True, capture_output=True, text=True)
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert payload["launch_mode"] == "api"
    assert payload["health"]["ok"] is True
    assert payload["audit_events"] >= 3
