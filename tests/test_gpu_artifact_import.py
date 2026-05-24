import json
import tarfile
from pathlib import Path

from flow_memory.neural.gpu_evidence import import_gpu_run_artifact


def test_gpu_artifact_import_extracts_safe_metadata_only(tmp_path: Path):
    source = tmp_path / "run-src"
    source.mkdir()
    (source / "validation.json").write_text(
        json.dumps(
            {
                "ok": True,
                "mode": "full",
                "results": [
                    {"name": "cli_neural", "ok": True},
                    {"name": "world_model_benchmark", "ok": True},
                    {"name": "full_pytest", "ok": True, "stdout_tail": "339 passed, 3 skipped"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (source / "gpu_info.json").write_text(
        json.dumps(
            {
                "gpu_name": "NVIDIA GeForce RTX 4090",
                "torch_version": "2.12.0+cu130",
                "cuda_available": True,
                "cuda_version": "13.0",
                "git_commit": "34c67f1",
            }
        ),
        encoding="utf-8",
    )
    (source / "metrics.json").write_text(json.dumps({"ok": True}), encoding="utf-8")
    (source / "model_card.md").write_text("# Smoke model\n\nTiny smoke model, not production.\n", encoding="utf-8")
    (source / "dummy.pt").write_bytes(b"weights are not release evidence")
    artifact = tmp_path / "flow-memory-cloud-gpu-run-001.tar.gz"
    with tarfile.open(artifact, "w:gz") as archive:
        archive.add(source, arcname="gpu-run")

    summary = import_gpu_run_artifact(artifact, tmp_path / "gpu_runs")

    assert summary["imported"] is True
    assert summary["skipped"] is False
    assert summary["environment"]["gpu_name"] == "NVIDIA GeForce RTX 4090"
    assert summary["environment"]["torch_version"] == "2.12.0+cu130"
    assert summary["environment"]["cuda_available"] is True
    assert summary["statuses"]["cli_neural"]["ok"] is True
    assert summary["statuses"]["benchmarks"]["ok"] is True
    assert summary["counts"]["checkpoints"] == 1

    run_dir = tmp_path / "gpu_runs" / "flow-memory-cloud-gpu-run-001"
    assert (run_dir / "summary.json").exists()
    assert (run_dir / "summary.md").exists()
    assert (run_dir / "hashes.json").exists()
    assert not (run_dir / "metadata" / "gpu-run" / "dummy.pt").exists()
    hashes = json.loads((run_dir / "hashes.json").read_text(encoding="utf-8"))
    assert any(record["path"].endswith("dummy.pt") for record in hashes["files"])
    assert any(record["reason"] == "non_metadata_or_binary" for record in hashes["skipped_files"])
