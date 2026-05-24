from flow_memory.neural.gpu_evidence import gpu_evidence_index, import_gpu_run_artifact
from flow_memory.release.evidence import build_evidence_documents


def test_gpu_evidence_index_handles_absent_directory(tmp_path):
    assert gpu_evidence_index(tmp_path)["ok"] is True
    assert gpu_evidence_index(tmp_path)["skipped"] is True


def test_release_evidence_includes_gpu_evidence(tmp_path):
    import_gpu_run_artifact(tmp_path / "missing.tar.gz", tmp_path / "release_evidence" / "gpu_runs")
    documents = build_evidence_documents(tmp_path)
    assert "gpu_evidence.json" in documents
