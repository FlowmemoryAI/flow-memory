import json
import subprocess
import sys
from pathlib import Path

from flow_memory.neural.artifacts import write_json
from flow_memory.neural.run_records import evaluate_neural_gpu_smoke

ROOT = Path(__file__).resolve().parents[1]


def test_neural_gpu_smoke_evaluation_passes_with_imported_gpu_evidence(tmp_path: Path):
    run_dir = tmp_path / "release_evidence" / "gpu_runs" / "run-001"
    write_json(
        run_dir / "summary.json",
        {
            "format": "flow-memory-neural-gpu-run-summary-v1",
            "run_id": "run-001",
            "imported": True,
            "skipped": False,
            "environment": {
                "gpu_name": "NVIDIA GeForce RTX 4090",
                "torch_version": "2.12.0+cu130",
                "cuda_available": True,
            },
            "statuses": {
                "cli_neural": {"ok": True, "status": "ok"},
                "benchmarks": {"ok": True, "status": "ok"},
            },
            "counts": {},
        },
    )

    decision = evaluate_neural_gpu_smoke(tmp_path)

    assert decision.ok is True
    assert decision.blockers == ()


def test_release_decision_script_accepts_neural_gpu_smoke_target():
    completed = subprocess.run(
        [sys.executable, "scripts/release_decision.py", "--root", str(ROOT), "--target", "neural-gpu-smoke"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    payload = json.loads(completed.stdout)
    assert payload["target"] == "neural-gpu-smoke"
    assert "neural_gpu_runs" in payload["required_evidence"]
    assert payload["classification"] in {"neural_gpu_smoke_candidate", "blocked_neural_gpu_smoke"}
