import json
import subprocess
import sys
from pathlib import Path

from scripts.check_release_api import check_release_api

ROOT = Path(__file__).resolve().parents[1]


def test_check_release_api_helper_uses_no_raw_artifacts():
    payload = check_release_api(require_scopes=True)
    assert payload["ok"] is True
    assert payload["requires_network_server"] is False
    assert payload["raw_artifacts_exposed"] is False


def test_check_release_api_script_writes_json(tmp_path):
    out = tmp_path / "release_api.json"
    completed = subprocess.run(
        [sys.executable, "scripts/check_release_api.py", "--require-scopes", "--json-out", str(out)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(completed.stdout)["ok"] is True
    assert json.loads(out.read_text(encoding="utf-8"))["ok"] is True
