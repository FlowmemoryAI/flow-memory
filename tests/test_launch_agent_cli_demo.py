import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(*args: str) -> dict:
    completed = subprocess.run([sys.executable, *args], cwd=ROOT, check=True, capture_output=True, text=True)
    return json.loads(completed.stdout)


def test_launch_local_agent_script_runs():
    payload = _run("scripts/launch_local_agent.py", "--goal", "Explore and report")
    assert payload["ok"] is True
    assert payload["launch_mode"] == "cli"
    assert payload["safety_authority"] == "policy_engine_and_approval_gate"


def test_launch_agent_cli_demo_runs():
    payload = _run("examples/launch_agent_cli_demo.py")
    assert payload["ok"] is True
    assert payload["launch_mode"] == "cli"
