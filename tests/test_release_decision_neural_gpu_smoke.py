from flow_memory.neural.gpu_evidence import import_gpu_run_artifact
from flow_memory.release.readiness import decide_release_readiness


def test_neural_gpu_smoke_release_target_declares_gpu_evidence(tmp_path):
    import_gpu_run_artifact(tmp_path / "missing.tar.gz", tmp_path / "release_evidence" / "gpu_runs")
    decision = decide_release_readiness(tmp_path, target="neural-gpu-smoke")
    assert decision.target == "neural-gpu-smoke"
    assert "gpu_evidence" in decision.required_evidence
