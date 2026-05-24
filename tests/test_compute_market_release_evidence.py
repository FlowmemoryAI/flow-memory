from flow_memory.release.compute_evidence import compute_market_evidence
from flow_memory.release.evidence import build_evidence_documents


def test_compute_market_release_evidence_includes_dry_run_invariants():
    evidence = compute_market_evidence()

    assert evidence["ok"] is True
    assert evidence["api_endpoints_present"] is True
    assert evidence["cli_commands_present"] is True
    assert evidence["dry_run_only_settlement_invariant"] is True
    assert evidence["no_private_keys_funds_broadcast_invariant"] is True
    assert evidence["policy_fail_closed_sample"]["ok"] is False


def test_release_bundle_includes_compute_market_evidence():
    docs = build_evidence_documents()

    assert "compute_market.json" in docs
    assert docs["compute_market.json"]["ok"] is True
