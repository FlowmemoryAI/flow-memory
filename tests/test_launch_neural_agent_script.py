import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_launch_neural_agent_script_runs_or_skips_torch_clearly():
    completed = subprocess.run(
        [sys.executable, "scripts/launch_neural_agent.py", "--backend", "tiny_torch", "--goal", "Explore and report"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert payload["backend"] == "tiny_torch"
    assert payload["safety_authority"] == "policy_engine_and_approval_gate"
    if payload["neural"].get("status") == "skipped":
        assert "torch" in payload["fallback_or_skip_reason"].lower()
