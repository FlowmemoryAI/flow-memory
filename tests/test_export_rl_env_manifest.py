import json
import subprocess
import sys
from pathlib import Path

from scripts.export_rl_env_manifest import export_rl_env_manifest

ROOT = Path(__file__).resolve().parents[1]


def test_export_rl_env_manifest_includes_adversarial_envs():
    payload = export_rl_env_manifest()
    names = {env["env_id"] for env in payload["envs"]}
    assert {"reputation_gaming", "sybil_risk", "colluding_verifier"} <= names
    assert payload["ok"] is True
    assert all(env["advisory_only"] is True for env in payload["envs"])


def test_export_rl_env_manifest_script_writes_json(tmp_path):
    out = tmp_path / "manifest.json"
    completed = subprocess.run(
        [sys.executable, "scripts/export_rl_env_manifest.py", "--out", str(out)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(completed.stdout)["ok"] is True
    assert json.loads(out.read_text(encoding="utf-8"))["env_count"] >= 10
