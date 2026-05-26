"""Proof of Learning ledger records derived from the Experience Graph."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from flow_memory.cognition.state import stable_id, utc_now

DEFAULT_PROOF_DIR = Path("artifacts/experience_graph/proofs")


@dataclass(frozen=True)
class ProofOfLearningRecord:
    proof_id: str
    agent_id: str
    experience_id: str
    prediction_id: str
    lesson_id: str
    contribution_id: str = ""
    prediction_error_before: float = 0.0
    prediction_error_after: float = 0.0
    error_delta: float = 0.0
    lesson_reuse_count: int = 0
    helped_agent_id: str = ""
    policy_compliance: float = 1.0
    private_payload_excluded: bool = True
    score: float = 0.0
    created_at: str = field(default_factory=utc_now)

    def as_record(self) -> dict[str, Any]:
        return {
            "proof_id": self.proof_id,
            "agent_id": self.agent_id,
            "experience_id": self.experience_id,
            "prediction_id": self.prediction_id,
            "lesson_id": self.lesson_id,
            "contribution_id": self.contribution_id,
            "prediction_error_before": round(self.prediction_error_before, 6),
            "prediction_error_after": round(self.prediction_error_after, 6),
            "error_delta": round(self.error_delta, 6),
            "lesson_reuse_count": self.lesson_reuse_count,
            "helped_agent_id": self.helped_agent_id,
            "policy_compliance": round(self.policy_compliance, 6),
            "private_payload_excluded": self.private_payload_excluded,
            "score": round(self.score, 6),
            "created_at": self.created_at,
            "safety_authority": "policy_engine_and_approval_gate",
        }


def build_proof_ledger(graph: Mapping[str, Any], root: str | Path = ".", *, write_artifact: bool = True) -> Mapping[str, Any]:
    nodes = tuple(dict(node) for node in graph.get("nodes", ()) if isinstance(node, Mapping))
    edges = tuple(dict(edge) for edge in graph.get("edges", ()) if isinstance(edge, Mapping))
    by_id = {str(node.get("node_id", "")): node for node in nodes}
    learned_edges = tuple(edge for edge in edges if edge.get("edge_type") == "learned")
    contributed_edges = tuple(edge for edge in edges if edge.get("edge_type") == "contributed")
    reused_edges = tuple(edge for edge in edges if edge.get("edge_type") == "reused")
    proofs: list[Mapping[str, Any]] = []
    for edge in learned_edges:
        source = by_id.get(str(edge.get("source_id", "")), {})
        target = by_id.get(str(edge.get("target_id", "")), {})
        agent_id = str(target.get("agent_id") or source.get("agent_id") or "proof-agent")
        experience_id = str(edge.get("evidence_ref", ""))
        error_meta = dict(source.get("metadata", {})) if isinstance(source.get("metadata", {}), Mapping) else {}
        before = float(error_meta.get("prediction_error", 0.0) or 0.0)
        after = max(0.0, before - float(edge.get("weight", 0.0) or 0.0) * 0.25)
        contribution_id = _matching_contribution_id(target, by_id, contributed_edges)
        reuse_count = sum(1 for item in reused_edges if item.get("source_id") == target.get("node_id") or item.get("target_id") == target.get("node_id"))
        score = _score(before, after, reuse_count, bool(contribution_id))
        proof = ProofOfLearningRecord(
            proof_id=stable_id("proof_of_learning", agent_id, experience_id, str(target.get("node_id", "")), contribution_id),
            agent_id=agent_id,
            experience_id=experience_id,
            prediction_id=str(error_meta.get("prediction_id", "")),
            lesson_id=str(target.get("ref_id", target.get("node_id", ""))),
            contribution_id=contribution_id,
            prediction_error_before=before,
            prediction_error_after=after,
            error_delta=before - after,
            lesson_reuse_count=reuse_count,
            policy_compliance=1.0,
            private_payload_excluded=True,
            score=score,
        ).as_record()
        proofs.append(proof)
    if not proofs and nodes:
        agent_id = str(next((node.get("agent_id") for node in nodes if node.get("agent_id")), "proof-agent"))
        proofs.append(ProofOfLearningRecord(
            proof_id=stable_id("proof_of_learning", agent_id, str(graph.get("graph_id", ""))),
            agent_id=agent_id,
            experience_id=str(graph.get("graph_id", "")),
            prediction_id="graph_summary",
            lesson_id="graph_summary",
            score=0.5,
        ).as_record())
    ledger = {
        "ok": True,
        "graph_id": graph.get("graph_id", ""),
        "proofs": tuple(proofs),
        "proof_count": len(proofs),
        "average_score": round(sum(float(item.get("score", 0.0) or 0.0) for item in proofs) / len(proofs), 6) if proofs else 0.0,
        "private_payload_excluded": True,
        "local_only": True,
        "safety_authority": "policy_engine_and_approval_gate",
    }
    if write_artifact:
        ledger = {**ledger, "write": write_proof_ledger(ledger, root=root)}
    return ledger


def write_proof_ledger(ledger: Mapping[str, Any], root: str | Path = ".", directory: str | Path = DEFAULT_PROOF_DIR) -> Mapping[str, Any]:
    root_path = Path(root).resolve()
    directory_path = root_path / directory
    directory_path.mkdir(parents=True, exist_ok=True)
    written = []
    for proof in ledger.get("proofs", ()):
        if not isinstance(proof, Mapping):
            continue
        path = directory_path / f"{_safe(str(proof.get('proof_id', 'proof')))}.json"
        path.write_text(json.dumps(dict(proof), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(_rel(root_path, path))
    return {"ok": True, "proof_count": len(written), "paths": tuple(written)}


def list_proofs(root: str | Path = ".", directory: str | Path = DEFAULT_PROOF_DIR) -> tuple[Mapping[str, Any], ...]:
    base = Path(root).resolve() / directory
    if not base.exists():
        return ()
    return tuple(_read_record(path) for path in sorted(base.glob("*.json")))


def get_proof(proof_id: str, root: str | Path = ".", directory: str | Path = DEFAULT_PROOF_DIR) -> Mapping[str, Any]:
    path = Path(root).resolve() / directory / f"{_safe(proof_id)}.json"
    if not path.exists():
        raise KeyError(f"unknown proof of learning record: {proof_id}")
    return _read_record(path)


def _matching_contribution_id(lesson: Mapping[str, Any], by_id: Mapping[str, Mapping[str, Any]], edges: tuple[Mapping[str, Any], ...]) -> str:
    node_id = str(lesson.get("node_id", ""))
    for edge in edges:
        if edge.get("source_id") == node_id:
            target = by_id.get(str(edge.get("target_id", "")), {})
            return str(target.get("ref_id", ""))
    return ""


def _score(before: float, after: float, reuse_count: int, contributed: bool) -> float:
    return max(0.0, min(1.0, 0.4 + max(0.0, before - after) * 0.6 + min(reuse_count, 3) * 0.08 + (0.1 if contributed else 0.0)))


def _safe(value: str) -> str:
    safe = "".join(ch for ch in value if ch.isalnum() or ch in {"-", "_", "."}).strip(".")
    if not safe:
        raise ValueError("identifier is required")
    return safe


def _read_record(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"proof file is not a JSON object: {path}")
    return dict(payload)


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
