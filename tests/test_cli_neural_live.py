import json
import subprocess
import sys


def _run_cli(*args: str) -> dict:
    completed = subprocess.run([sys.executable, "-m", "flow_memory", *args], check=True, capture_output=True, text=True)
    return json.loads(completed.stdout)


def test_cli_neural_live_step_outputs_session_and_step():
    payload = _run_cli("neural", "live", "step", "--backend", "tiny_torch", "--goal", "Explore and report")

    assert payload["ok"] is True
    assert payload["session"]["session_id"]
    assert payload["step"]["local_only"] is True
    assert payload["step"]["external_model_calls"] is False


def test_cli_agent_neural_live_attaches_runtime_metadata():
    payload = _run_cli("--neural", "tiny_torch", "--neural-live", "--json", "Explore and report")

    assert payload["output"]["neural"]["session_id"]
    assert payload["output"]["neural"]["live_step"]["local_only"] is True
