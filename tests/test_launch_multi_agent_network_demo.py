import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(*args: str) -> dict:
    completed = subprocess.run([sys.executable, *args], cwd=ROOT, check=True, capture_output=True, text=True)
    return json.loads(completed.stdout)


def test_launch_local_agent_network_script_runs_all_scenarios():
    payload = _run("scripts/launch_local_agent_network.py")
    assert payload["ok"] is True
    scenarios = {item["scenario"] for item in payload["report"]["scenarios"]}
    assert {"basic-economy", "neural-agent", "rl-training", "dispute-slashing"} <= scenarios


def test_launch_multi_agent_network_demo_runs():
    payload = _run("examples/launch_multi_agent_network_demo.py")
    assert payload["ok"] is True
    assert payload["launch_mode"] == "multi_agent_network"
