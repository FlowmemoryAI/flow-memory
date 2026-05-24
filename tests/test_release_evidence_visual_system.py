from pathlib import Path

from flow_memory.release.evidence import build_evidence_documents
from flow_memory.release.visual_evidence import verify_visual_system_evidence, visual_system_evidence


def test_visual_system_evidence_detects_mission_control_assets():
    root = Path(__file__).resolve().parents[1]
    evidence = visual_system_evidence(root)

    assert evidence["ok"] is True
    assert evidence["replay"]["ok"] is True
    assert evidence["replay"]["agent_count"] >= 1
    assert evidence["replay"]["task_count"] >= 1
    assert evidence["endpoints"]["ok"] is True
    assert verify_visual_system_evidence(evidence)["ok"] is True


def test_visual_system_evidence_reports_missing_replay(tmp_path):
    evidence = visual_system_evidence(tmp_path)

    assert evidence["ok"] is False
    verification = verify_visual_system_evidence(evidence)
    assert verification["ok"] is False
    assert "dashboard/src/mock-data/local-network-replay.json" in verification["missing_files"]


def test_release_evidence_includes_visual_system_document():
    root = Path(__file__).resolve().parents[1]
    documents = build_evidence_documents(root)

    assert "visual_system.json" in documents
    assert documents["visual_system.json"]["ok"] is True
