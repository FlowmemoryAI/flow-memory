import json
import subprocess
import sys
from pathlib import Path

from scripts.validate_local_network_report import validate_local_network_report

ROOT = Path(__file__).resolve().parents[1]


def test_validate_local_network_report_accepts_generated_report(tmp_path):
    out = tmp_path / "network.json"
    subprocess.run(
        [sys.executable, "scripts/run_local_network.py", "--scenario", "all", "--json-out", str(out)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    result = validate_local_network_report(out)
    assert result["ok"] is True
    assert result["scenario_count"] >= 4
    assert result["participant_count"] >= 3


def test_validate_local_network_report_rejects_missing_scenarios(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"ok": True, "scenarios": [], "topology": {"participants": []}}), encoding="utf-8")
    result = validate_local_network_report(bad)
    assert result["ok"] is False
    assert "network_scenarios_missing" in result["blockers"]
