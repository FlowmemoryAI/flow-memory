import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_public_alpha_launch_evidence_export_and_verify(tmp_path):
    quick = ROOT / "artifacts" / "full_system" / "quick_report.json"
    network = ROOT / "artifacts" / "network" / "local_network_report.json"
    if not quick.exists() or not network.exists() or json.loads(quick.read_text(encoding="utf-8")).get("ok") is not True:
        subprocess.run([sys.executable, "scripts/test_full_system.py", "--quick", "--json-out", str(quick)], cwd=ROOT, check=True, capture_output=True, text=True)
    launch_report = ROOT / "artifacts" / "public_alpha_launch" / "launch_report.json"
    if not launch_report.exists() or json.loads(launch_report.read_text(encoding="utf-8")).get("ok") is not True:
        subprocess.run([sys.executable, "scripts/test_public_alpha_launch.py"], cwd=ROOT, check=True, capture_output=True, text=True)
    out = tmp_path / "public_alpha_launch.json"
    exported = subprocess.run([sys.executable, "scripts/export_public_alpha_launch_evidence.py", "--out", str(out)], cwd=ROOT, check=True, capture_output=True, text=True)
    export_payload = json.loads(exported.stdout)
    assert export_payload["ok"] is True
    verified = subprocess.run([sys.executable, "scripts/verify_public_alpha_launch_evidence.py", str(out)], cwd=ROOT, check=True, capture_output=True, text=True)
    verify_payload = json.loads(verified.stdout)
    assert verify_payload["ok"] is True
    assert verify_payload["evidence"]["real_funds_used"] is False
    assert verify_payload["evidence"]["dashboard_mock_snapshot"]["ok"] is True
    assert verify_payload["evidence"]["dashboard_mock_snapshot"]["mock_data_only"] is True


def test_public_alpha_launch_evidence_tamper_detection(tmp_path):
    evidence = {"git_commit": "abc", "full_system_quick": {"ok": True}, "docs": {}, "secret_scan": "no obvious secret patterns found", "real_funds_used": False, "hash": "bad"}
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(evidence), encoding="utf-8")
    completed = subprocess.run([sys.executable, "scripts/verify_public_alpha_launch_evidence.py", str(path)], cwd=ROOT, capture_output=True, text=True)
    payload = json.loads(completed.stdout)
    assert completed.returncode == 1
    assert "launch_evidence_hash_mismatch" in payload["blockers"]
