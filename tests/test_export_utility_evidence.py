import json
import subprocess
import sys
from pathlib import Path

from scripts.export_utility_evidence import build_utility_evidence

ROOT = Path(__file__).resolve().parents[1]


def test_build_utility_evidence_collects_public_alpha_utilities():
    payload = build_utility_evidence(ROOT)
    assert payload["ok"] is True
    assert payload["dashboard_api"]["ok"] is True
    assert payload["release_api"]["ok"] is True
    assert payload["payment_ledger_demo"]["real_funds_used"] is False
    assert payload["hash"]


def test_export_utility_evidence_script_writes_json(tmp_path):
    out = tmp_path / "utility_evidence.json"
    completed = subprocess.run(
        [sys.executable, "scripts/export_utility_evidence.py", "--out", str(out)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(completed.stdout)["ok"] is True
    assert json.loads(out.read_text(encoding="utf-8"))["raw_artifacts_exposed"] is False
