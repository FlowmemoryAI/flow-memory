import json
import subprocess
import sys
from pathlib import Path

from scripts.check_dashboard_api import check_dashboard_api

ROOT = Path(__file__).resolve().parents[1]


def test_check_dashboard_api_helper_reports_mock_snapshot() -> None:
    payload = check_dashboard_api(require_scopes=True)
    assert payload["ok"] is True
    assert payload["mock_data_only"] is True
    assert payload["raw_artifacts_exposed"] is False
    assert "payments" in payload["records"]


def test_check_dashboard_api_script_writes_json(tmp_path: Path) -> None:
    out = tmp_path / "dashboard_api.json"
    completed = subprocess.run(
        [sys.executable, "scripts/check_dashboard_api.py", "--require-scopes", "--json-out", str(out)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(completed.stdout)["ok"] is True
    assert json.loads(out.read_text(encoding="utf-8"))["record_count"] >= 6
