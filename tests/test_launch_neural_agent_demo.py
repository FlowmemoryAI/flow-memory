import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_launch_neural_agent_demo_runs() -> None:
    completed = subprocess.run(
        [sys.executable, "examples/launch_neural_agent_demo.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["python_agent"]["ok"] is True
    assert payload["flowlang_agent"]["ok"] is True
    assert payload["safety_authority"] == "policy_engine_and_approval_gate"
    assert "--neural tiny_torch" in payload["commands"]["tiny_torch"]
