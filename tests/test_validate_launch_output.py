import json
import subprocess
import sys
from pathlib import Path

from scripts.validate_launch_output import validate_launch_output

ROOT = Path(__file__).resolve().parents[1]


def test_validate_launch_output_accepts_launch_script_json(tmp_path):
    out = tmp_path / "launch.json"
    subprocess.run(
        [sys.executable, "scripts/launch_local_agent.py", "--goal", "Explore and report", "--json-out", str(out)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    result = validate_launch_output(out)
    assert result["ok"] is True
    assert result["launch_mode"] == "cli"


def test_validate_launch_output_rejects_missing_safety_authority(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"ok": True, "launch_mode": "neural", "neural": {}}), encoding="utf-8")
    result = validate_launch_output(bad)
    assert result["ok"] is False
    assert "safety_authority_missing" in result["blockers"]
