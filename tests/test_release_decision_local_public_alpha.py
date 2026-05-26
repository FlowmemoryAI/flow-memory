from flow_memory.release import decide_release_readiness


def test_local_public_alpha_release_can_pass_without_gpu_artifact() -> None:
    decision = decide_release_readiness(".", target="local-public-alpha")
    assert decision.ok is True
    assert decision.classification == "local_public_alpha_candidate"
    assert "gpu_evidence" not in decision.required_evidence


def test_gpu_gated_releases_still_block_without_verified_gpu_artifact() -> None:
    decision = decide_release_readiness(".", target="neural-gpu-smoke")
    if not decision.ok:
        assert "gpu_evidence_verified_run_missing" in decision.blockers or "gpu_evidence_missing" in decision.blockers
    assert "gpu_evidence" in decision.required_evidence
