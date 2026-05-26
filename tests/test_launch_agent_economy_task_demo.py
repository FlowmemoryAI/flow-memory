import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_launch_agent_economy_task_demo_runs_full_lifecycle() -> None:
    completed = subprocess.run([sys.executable, "examples/launch_agent_economy_task_demo.py"], cwd=ROOT, check=True, capture_output=True, text=True)
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert "settle" in payload["lifecycle"]
    assert payload["real_funds_used"] is False
    assert payload["reputation"] > 0
