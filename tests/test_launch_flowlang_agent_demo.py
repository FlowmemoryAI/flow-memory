import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(*args: str) -> dict:
    completed = subprocess.run([sys.executable, *args], cwd=ROOT, check=True, capture_output=True, text=True)
    return json.loads(completed.stdout)


def test_launch_flowlang_agent_script_runs():
    payload = _run("scripts/launch_flowlang_agent.py", "examples/flowlang_agent.flow", "--goal", "Run the declared agent")
    assert payload["ok"] is True
    assert payload["launch_mode"] == "flowlang"


def test_launch_flowlang_agent_demo_runs():
    payload = _run("examples/launch_flowlang_agent_demo.py")
    assert payload["ok"] is True
    assert payload["launch_mode"] == "flowlang"
