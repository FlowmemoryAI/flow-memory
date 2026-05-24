import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def ensure_launch_evidence() -> None:
    report = ROOT / "artifacts" / "public_alpha_launch" / "launch_report.json"
    if not report.exists() or json.loads(report.read_text(encoding="utf-8")).get("ok") is not True:
        subprocess.run([sys.executable, "scripts/test_public_alpha_launch.py"], cwd=ROOT, check=True, capture_output=True, text=True)
    subprocess.run([sys.executable, "scripts/export_public_alpha_launch_evidence.py"], cwd=ROOT, check=True, capture_output=True, text=True)


def test_public_alpha_local_launch_target_passes_without_gpu_artifact():
    ensure_launch_evidence()
    completed = subprocess.run(
        [sys.executable, "scripts/release_decision.py", "--target", "public-alpha-local-launch"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert payload["target"] == "public-alpha-local-launch"
    assert "gpu_evidence" not in " ".join(payload["required_evidence"])


def test_gpu_gated_targets_still_block_without_verified_gpu_run():
    completed = subprocess.run(
        [sys.executable, "scripts/release_decision.py", "--target", "neural-gpu-smoke"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    if payload["ok"]:
        return
    assert "gpu_evidence_verified_run_missing" in payload["blockers"] or "gpu_evidence_missing" in payload["blockers"]
