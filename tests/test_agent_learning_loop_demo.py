import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(*args: str) -> dict:
    completed = subprocess.run([sys.executable, *args], cwd=ROOT, check=True, capture_output=True, text=True)
    return json.loads(completed.stdout)


def test_agent_learning_loop_script_runs():
    payload = _run("scripts/run_agent_learning_loop.py")
    assert payload["episodes"] >= 2
    assert payload["success_rate"] > 0
    assert payload["memory_count"] >= 2


def test_agent_learning_loop_demo_runs():
    payload = _run("examples/agent_learning_loop_demo.py")
    assert payload["before_after"]["improvement"]["ok"] is True


def test_agent_improves_with_memory_demo_runs():
    payload = _run("examples/agent_improves_with_memory_demo.py")
    assert payload["ok"] is True
    assert payload["after_memory_count"] > payload["before_memory_count"]


def test_agent_improves_with_rl_demo_runs():
    payload = _run("examples/agent_improves_with_rl_demo.py")
    assert payload["ok"] is True
    assert payload["advisory_only"] is True
