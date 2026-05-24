import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
from scripts.test_full_system import ROOT as SCRIPT_ROOT, full_checks


def test_full_system_quick_report_passes(tmp_path):
    out = tmp_path / "quick_report.json"
    completed = subprocess.run(
        [sys.executable, "scripts/test_full_system.py", "--quick", "--json-out", str(out)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert payload["mode"] == "quick"
    names = {item["name"] for item in payload["results"]}
    assert {"cli_agent", "flowlang_agent", "neural_agent", "local_network", "learning_loop", "release_api", "visual_replay_export", "visual_api", "release_local"} <= names
    assert out.exists()
    assert out.with_suffix(".md").exists()


def test_full_system_full_checks_include_cargo_workspace_cwd():
    checks = {check.name: check for check in full_checks()}
    assert "cargo_test" in checks
    assert checks["cargo_test"].command == ("cargo", "test")
    assert checks["cargo_test"].command_cwd == SCRIPT_ROOT / "rust" / "flow-memory-core"
