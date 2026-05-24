import json
from pathlib import Path

from flow_memory.release import export_release_evidence, verify_release_evidence

ROOT = Path(__file__).resolve().parents[1]


def test_release_evidence_bundle_includes_neural_gpu_runs(tmp_path: Path):
    out = tmp_path / "evidence"
    bundle = export_release_evidence(ROOT, out)
    verified = verify_release_evidence(out)

    assert "neural_gpu_runs.json" in bundle.index["files"]
    assert bundle.index["bundle_hash"] == verified.index["bundle_hash"]
    payload = json.loads((out / "neural_gpu_runs.json").read_text(encoding="utf-8"))
    assert payload["format"] == "flow-memory-neural-gpu-runs-v1"
    assert "runs" in payload
