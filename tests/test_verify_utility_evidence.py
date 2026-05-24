import json
import subprocess
import sys
from pathlib import Path

from scripts.export_utility_evidence import build_utility_evidence
from scripts.verify_utility_evidence import verify_utility_evidence

ROOT = Path(__file__).resolve().parents[1]


def test_verify_utility_evidence_accepts_export(tmp_path):
    path = tmp_path / "utility.json"
    path.write_text(json.dumps(build_utility_evidence(ROOT), indent=2, sort_keys=True), encoding="utf-8")
    result = verify_utility_evidence(path)
    assert result["ok"] is True
    assert result["blockers"] == ()


def test_verify_utility_evidence_detects_tampering(tmp_path):
    payload = dict(build_utility_evidence(ROOT))
    payload["real_funds_used"] = True
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    result = verify_utility_evidence(path)
    assert result["ok"] is False
    assert "utility_evidence_hash_mismatch" in result["blockers"]
    assert "real_funds_flag_not_false" in result["blockers"]


def test_verify_utility_evidence_script(tmp_path):
    out = tmp_path / "utility.json"
    subprocess.run([sys.executable, "scripts/export_utility_evidence.py", "--out", str(out)], cwd=ROOT, check=True, capture_output=True, text=True)
    completed = subprocess.run([sys.executable, "scripts/verify_utility_evidence.py", str(out)], cwd=ROOT, check=True, capture_output=True, text=True)
    assert json.loads(completed.stdout)["ok"] is True
