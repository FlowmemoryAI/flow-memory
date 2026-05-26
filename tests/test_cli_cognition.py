import json
import subprocess
import sys


def _run_cli(*args: str) -> dict:
    completed = subprocess.run([sys.executable, "-m", "flow_memory", *args], check=True, capture_output=True, text=True)
    return json.loads(completed.stdout)


def test_cli_cognition_predict_outputs_prediction_without_experience_path():
    payload = _run_cli("cognition", "predict", "--goal", "verify dashboard", "--action", "check mission-control route", "--json")

    assert payload["ok"] is True
    assert payload["prediction"]["prediction_id"].startswith("prediction_record_")
    assert payload["selected_action"]["description"]
    assert "experience_path" not in payload


def test_cli_cognition_tick_and_error_listing_work():
    tick = _run_cli("cognition", "tick", "--agent", "cli-test-agent", "--goal", "verify dashboard", "--action", "check mission-control route", "--json")
    errors = _run_cli("cognition", "prediction-errors", "list", "--json")

    assert tick["ok"] is True
    assert tick["experience"]["experience_id"].startswith("experience_")
    assert tick["prediction_error"]["error_id"].startswith("prediction_error_")
    assert errors["ok"] is True
    assert errors["count"] >= 1
