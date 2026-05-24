import io, json, tarfile
from pathlib import Path
from flow_memory.neural.gpu_evidence import DEFAULT_RUN_ID, import_gpu_run_artifact


def _tar(path: Path):
    with tarfile.open(path, "w:gz") as tar:
        members = {
            "artifacts/cloud_gpu_run_001/gpu_info.txt": b"python: 3.12\ntorch: 2.12.0+cu130\ncuda available: True\ncuda version: 13.0\ngpu: NVIDIA GeForce RTX 4090\n",
            "artifacts/cloud_gpu_run_001/git_commit.txt": b"948f70d\n",
            "artifacts/cloud_gpu_run_001/validation_summary.txt": b"339 passed, 3 skipped\n",
            "artifacts/cloud_gpu_run_001/cli_neural.json": b'{"neural":{"backend":"tiny_torch","status":"available"}}',
            "artifacts/cloud_gpu_run_001/neural_plan_scoring_benchmark.json": b'{"ok":true,"mean_score":0.7}',
            "artifacts/cloud_gpu_run_001/model.pt": b"not copied",
        }
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))


def test_import_gpu_run_artifact_extracts_safe_metadata(tmp_path):
    tarball = tmp_path / "flow-memory-cloud-gpu-run-001.tar.gz"
    _tar(tarball)
    summary = import_gpu_run_artifact(tarball, tmp_path / "runs")
    out = tmp_path / "runs" / DEFAULT_RUN_ID
    assert summary.gpu_name == "NVIDIA GeForce RTX 4090"
    assert summary.cuda_available is True
    assert summary.cli_neural_backend == "tiny_torch"
    assert (out / "summary.json").exists()
    assert not (out / "model.pt").exists()


def test_missing_gpu_artifact_is_explicitly_skipped(tmp_path):
    summary = import_gpu_run_artifact(tmp_path / "missing.tar.gz", tmp_path / "runs")
    record = json.loads((tmp_path / "runs" / DEFAULT_RUN_ID / "summary.json").read_text())
    assert summary.skipped is True
    assert record["ok"] is True
    assert "artifact not present" in record["reason"]
