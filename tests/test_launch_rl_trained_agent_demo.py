import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_launch_rl_trained_agent_demo_runs_and_keeps_safety_authoritative():
    completed = subprocess.run([sys.executable, "examples/launch_rl_trained_agent_demo.py"], cwd=ROOT, check=True, capture_output=True, text=True)
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert payload["training"]["improved"] is True
    assert payload["rl_can_bypass_safety"] is False
    assert payload["safety_authority"] == "policy_engine_and_approval_gate"
