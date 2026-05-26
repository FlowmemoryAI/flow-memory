from __future__ import annotations

import json
from pathlib import Path

from flow_memory.release.evidence import build_evidence_documents
from flow_memory.release.readiness import decide_release_readiness
from flow_memory.release.rl_evidence import rl_benchmark_evidence, verify_rl_benchmark_evidence


def test_rl_benchmark_evidence_hashes_benchmark_files(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts" / "rl"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "rl_policy_comparison_benchmark.json").write_text(json.dumps({"ok": True, "env_id": "safety_gate", "best_policy": "heuristic"}))
    evidence = rl_benchmark_evidence(tmp_path)
    assert evidence["benchmark_count"] == 1
    record = evidence["benchmarks"][0]
    assert len(record["sha256"]) == 64
    assert verify_rl_benchmark_evidence(evidence)["ok"] is True


def test_release_evidence_documents_include_rl_benchmarks(tmp_path: Path) -> None:
    docs = build_evidence_documents(tmp_path)
    assert "rl_benchmarks.json" in docs


def test_public_alpha_neural_release_target_declares_rl_benchmark_evidence(tmp_path: Path) -> None:
    decision = decide_release_readiness(tmp_path, target="public-alpha-neural")
    assert decision.target == "public-alpha-neural"
    assert "rl_benchmarks" in decision.required_evidence
    assert "rl_benchmark_evidence_missing" in decision.blockers
