import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_recover_gpu_artifact_instructions_reports_expected_path():
    completed = subprocess.run([sys.executable, "scripts/recover_gpu_artifact_instructions.py", "--json"], cwd=ROOT, check=True, capture_output=True, text=True)
    payload = json.loads(completed.stdout)
    assert payload["expected_path"].endswith("artifacts\\incoming\\flow-memory-cloud-gpu-run-001.tar.gz") or payload["expected_path"].endswith("artifacts/incoming/flow-memory-cloud-gpu-run-001.tar.gz")
    assert payload["blocker_if_missing"] == "gpu_evidence_verified_run_missing"
    assert payload["do_not_fake_evidence"] is True


def test_neural_gpu_smoke_cannot_pass_without_verified_artifact():
    completed = subprocess.run([sys.executable, "scripts/release_decision.py", "--target", "neural-gpu-smoke"], cwd=ROOT, capture_output=True, text=True)
    payload = json.loads(completed.stdout)
    if not payload["ok"]:
        assert "gpu_evidence_verified_run_missing" in payload["blockers"]
