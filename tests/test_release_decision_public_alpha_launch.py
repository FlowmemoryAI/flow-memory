from pathlib import Path

from flow_memory.release import decide_release_readiness

ROOT = Path(__file__).resolve().parents[1]


def test_public_alpha_launch_release_target_uses_imported_gpu_evidence():
    decision = decide_release_readiness(ROOT, target="public-alpha-launch")
    assert decision.target == "public-alpha-launch"
    assert "full_system_quick" in decision.required_evidence
    assert "gpu_evidence" in decision.required_evidence
    assert decision.ok is True
    assert "gpu_evidence_verified_run_missing" not in decision.blockers
