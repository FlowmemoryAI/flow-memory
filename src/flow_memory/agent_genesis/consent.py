"""Consent model for opt-in network learning."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from flow_memory.cognition.state import stable_id, utc_now

DEFAULT_CONSENT_DIR = Path("artifacts/genesis/consents")
CONSENT_MODES = ("private_only", "sanitized_lessons", "anonymous_benchmark_traces", "public_agent_genome", "compute_node_contributor")


@dataclass(frozen=True)
class NetworkLearningConsent:
    consent_id: str
    user_id: str
    agent_id: str
    mode: str = "private_only"
    allowed_record_types: tuple[str, ...] = ()
    raw_payload_allowed: bool = False
    private_memory_allowed: bool = False
    anonymization_required: bool = True
    revocable: bool = True
    accepted_at: str = field(default_factory=utc_now)
    consent_proof: str = ""

    def as_record(self) -> dict[str, Any]:
        return {
            "consent_id": self.consent_id,
            "user_id": self.user_id,
            "agent_id": self.agent_id,
            "mode": self.mode,
            "allowed_record_types": self.allowed_record_types,
            "raw_payload_allowed": self.raw_payload_allowed,
            "private_memory_allowed": self.private_memory_allowed,
            "anonymization_required": self.anonymization_required,
            "revocable": self.revocable,
            "accepted_at": self.accepted_at,
            "consent_proof": self.consent_proof,
        }


def create_consent(*, user_id: str, agent_id: str, mode: str = "private_only") -> NetworkLearningConsent:
    if mode not in CONSENT_MODES:
        raise ValueError(f"unknown network learning consent mode: {mode}")
    allowed = _allowed_types(mode)
    consent_id = stable_id("network_learning_consent", user_id, agent_id, mode)
    return NetworkLearningConsent(
        consent_id=consent_id,
        user_id=user_id,
        agent_id=agent_id,
        mode=mode,
        allowed_record_types=allowed,
        raw_payload_allowed=False,
        private_memory_allowed=False,
        anonymization_required=mode != "private_only",
        consent_proof=stable_id("consent_proof", user_id, agent_id, mode),
    )


def write_consent(consent: NetworkLearningConsent, root: str | Path = ".", directory: str | Path = DEFAULT_CONSENT_DIR) -> dict[str, Any]:
    payload = consent.as_record()
    path = _path(root, directory, consent.agent_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"ok": True, "agent_id": consent.agent_id, "consent_id": consent.consent_id, "path": _rel(Path(root).resolve(), path), "record": payload}


def get_consent(agent_id: str, root: str | Path = ".", directory: str | Path = DEFAULT_CONSENT_DIR) -> dict[str, Any]:
    path = _path(root, directory, agent_id)
    if not path.exists():
        raise KeyError(f"unknown consent: {agent_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def _allowed_types(mode: str) -> tuple[str, ...]:
    if mode == "private_only":
        return ()
    if mode == "sanitized_lessons":
        return ("consolidated_lesson", "human_teaching_event")
    if mode == "anonymous_benchmark_traces":
        return ("benchmark_result", "prediction_error", "policy_denial")
    if mode == "public_agent_genome":
        return ("public_genome",)
    if mode == "compute_node_contributor":
        return ("benchmark_result", "compute_node_capability")
    return ()


def _path(root: str | Path, directory: str | Path, agent_id: str) -> Path:
    safe = "".join(ch for ch in agent_id if ch.isalnum() or ch in {"-", "_", "."}).strip(".")
    if not safe:
        raise ValueError("agent_id is required")
    return Path(root).resolve() / directory / f"{safe}.json"


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
