import io
import tarfile

from flow_memory.neural.gpu_evidence import import_gpu_run_artifact
from flow_memory.release.readiness import decide_release_readiness


def _write_real_gpu_tarball(path):
    with tarfile.open(path, "w:gz") as tar:
        members = {
            "gpu_info.txt": b"python: 3.10\ntorch: 2.12.0+cu130\ncuda available: True\ncuda version: 13.0\ngpu: NVIDIA GeForce RTX 4090\n",
            "git_commit.txt": b"948f70d\n",
            "validation_summary.txt": b"339 passed, 3 skipped\n",
            "cli_neural.json": b'{"neural":{"backend":"tiny_torch","status":"available"}}',
        }
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))


def test_neural_gpu_smoke_release_target_declares_gpu_evidence(tmp_path):
    import_gpu_run_artifact(tmp_path / "missing.tar.gz", tmp_path / "release_evidence" / "gpu_runs")
    decision = decide_release_readiness(tmp_path, target="neural-gpu-smoke")
    assert decision.target == "neural-gpu-smoke"
    assert "gpu_evidence" in decision.required_evidence
    assert "gpu_evidence_verified_run_missing" in decision.blockers


def test_neural_gpu_smoke_release_target_accepts_verified_gpu_run(tmp_path):
    tarball = tmp_path / "flow-memory-cloud-gpu-run-001.tar.gz"
    _write_real_gpu_tarball(tarball)
    import_gpu_run_artifact(tarball, tmp_path / "release_evidence" / "gpu_runs")
    decision = decide_release_readiness(tmp_path, target="neural-gpu-smoke")
    assert "gpu_evidence_verified_run_missing" not in decision.blockers
