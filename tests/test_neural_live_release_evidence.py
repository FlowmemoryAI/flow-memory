from flow_memory.release.evidence import build_evidence_documents
from flow_memory.release.neural_live_evidence import neural_live_evidence


def test_neural_live_evidence_reports_local_runtime_and_invariants():
    evidence = neural_live_evidence()

    assert evidence["ok"] is True
    assert evidence["neural_live_runtime_available"] is True
    assert evidence["neural_step_loop_validated"] is True
    assert evidence["learning_loop_validated"] is True
    assert evidence["visual_telemetry_validated"] is True
    assert evidence["vjepa2_status"] == "adapter_seam"
    assert evidence["videomae_status"] == "adapter_seam"
    assert evidence["sample_checkpoint"]["raw_weights_written"] is False


def test_release_evidence_includes_neural_live_agents_document():
    documents = build_evidence_documents()

    assert "neural_live_agents.json" in documents
    assert documents["neural_live_agents.json"]["ok"] is True
