import json
import subprocess
import sys
from pathlib import Path

from scripts.check_visual_api import check_visual_api

ROOT = Path(__file__).resolve().parents[1]


def test_check_visual_api_in_process() -> None:
    payload = check_visual_api(require_scopes=True)
    assert payload["ok"] is True
    assert payload["raw_artifacts_exposed"] is False


def test_check_visual_api_script() -> None:
    completed = subprocess.run([sys.executable, "scripts/check_visual_api.py", "--require-scopes"], cwd=ROOT, check=True, capture_output=True, text=True)
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert payload["scenario_status"] == 200
