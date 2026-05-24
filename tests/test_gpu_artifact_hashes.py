import json
import tarfile
from pathlib import Path

from flow_memory.neural.gpu_evidence import import_gpu_run_artifact, verify_gpu_run


def test_gpu_run_verification_checks_extracted_metadata_hashes(tmp_path: Path):
    source = tmp_path / "run-src"
    source.mkdir()
    (source / "validation.json").write_text(json.dumps({"ok": True, "results": []}), encoding="utf-8")
    artifact = tmp_path / "run.tar.gz"
    with tarfile.open(artifact, "w:gz") as archive:
        archive.add(source, arcname="run")
    import_gpu_run_artifact(artifact, tmp_path / "gpu_runs", run_id="run-001")
    run_dir = tmp_path / "gpu_runs" / "run-001"

    assert verify_gpu_run(run_dir)["ok"] is True

    metadata_path = run_dir / "metadata" / "run" / "validation.json"
    metadata_path.write_text(json.dumps({"ok": False, "results": []}), encoding="utf-8")

    result = verify_gpu_run(run_dir)
    assert result["ok"] is False
    assert any("metadata hash mismatch" in error for error in result["errors"])
