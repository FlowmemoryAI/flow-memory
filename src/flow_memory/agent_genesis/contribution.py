"""Sanitized network contribution protocol for Agent Genesis."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from flow_memory.cognition.state import stable_id, utc_now

DEFAULT_CONTRIBUTION_DIR = Path("artifacts/genesis/contributions")
CONTRIBUTION_TYPES = ("prediction_error", "experience", "consolidated_lesson", "benchmark_result", "policy_denial", "memory_retrieval_signal", "public_genome", "human_teaching_event")


@dataclass(frozen=True)
class NetworkContribution:
    contribution_id: str
    agent_id: str
    user_id: str
    source_record_id: str
    contribution_type: str
    consent_id: str
    privacy_mode: str
    sanitized_payload: Mapping[str, Any]
    raw_payload_excluded: bool = True
    usefulness_score: float = 0.0
    validation_status: str = "pending"
    created_at: str = field(default_factory=utc_now)

    def as_record(self) -> dict[str, Any]:
        return {
            "contribution_id": self.contribution_id,
            "agent_id": self.agent_id,
            "user_id": self.user_id,
            "source_record_id": self.source_record_id,
            "contribution_type": self.contribution_type,
            "consent_id": self.consent_id,
            "privacy_mode": self.privacy_mode,
            "sanitized_payload": dict(self.sanitized_payload),
            "raw_payload_excluded": self.raw_payload_excluded,
            "usefulness_score": self.usefulness_score,
            "validation_status": self.validation_status,
            "created_at": self.created_at,
        }


def sanitize_contribution(payload: Mapping[str, Any], contribution_type: str) -> Mapping[str, Any]:
    allowed_keys = {
        "prediction_error": ("error_type", "prediction_error", "lesson", "memory_tags"),
        "experience": ("goal", "lesson", "memory_tags", "prediction_error"),
        "consolidated_lesson": ("title", "summary", "domain", "tags", "recommended_future_action", "usefulness_score"),
        "benchmark_result": ("benchmark_id", "scenario", "metrics", "ok"),
        "policy_denial": ("reason", "mode", "authority", "memory_tags"),
        "memory_retrieval_signal": ("query_tags", "hit_rate", "lesson_reused"),
        "public_genome": ("genome_id", "archetype_id", "purpose", "instincts", "boundaries", "benchmark_refs"),
        "human_teaching_event": ("correction_type", "lesson", "applies_to_tags"),
    }.get(contribution_type, ())
    sanitized = {key: payload.get(key) for key in allowed_keys if key in payload}
    sanitized["raw_private_payload_excluded"] = True
    return sanitized


def create_contribution(
    *,
    agent_id: str,
    user_id: str,
    source_record_id: str,
    contribution_type: str,
    consent: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> NetworkContribution:
    if contribution_type not in CONTRIBUTION_TYPES:
        raise ValueError(f"unknown contribution type: {contribution_type}")
    mode = str(consent.get("mode", "private_only"))
    allowed = tuple(consent.get("allowed_record_types", ()))
    validation = "private_only" if mode == "private_only" else "accepted" if contribution_type in allowed else "denied_by_consent"
    sanitized = sanitize_contribution(payload, contribution_type) if validation == "accepted" else {"raw_private_payload_excluded": True, "denied_reason": validation}
    contribution_id = stable_id("network_contribution", agent_id, user_id, source_record_id, contribution_type, str(sanitized))
    return NetworkContribution(
        contribution_id=contribution_id,
        agent_id=agent_id,
        user_id=user_id,
        source_record_id=source_record_id,
        contribution_type=contribution_type,
        consent_id=str(consent.get("consent_id", "")),
        privacy_mode=mode,
        sanitized_payload=sanitized,
        raw_payload_excluded=True,
        usefulness_score=float(payload.get("usefulness_score", payload.get("prediction_accuracy_after", 0.0)) or 0.0),
        validation_status=validation,
    )


def validate_contribution(record: NetworkContribution | Mapping[str, Any]) -> tuple[str, ...]:
    payload = record.as_record() if isinstance(record, NetworkContribution) else dict(record)
    errors: list[str] = []
    if payload.get("raw_payload_excluded") is not True:
        errors.append("raw payload must be excluded")
    sanitized = dict(payload.get("sanitized_payload", {})) if isinstance(payload.get("sanitized_payload", {}), Mapping) else {}
    forbidden = {"raw_private_content", "private_memory", "secret", "token", "private_key"}
    if forbidden.intersection(sanitized):
        errors.append("sanitized contribution includes private fields")
    return tuple(errors)


def write_contribution(record: NetworkContribution | Mapping[str, Any], root: str | Path = ".", directory: str | Path = DEFAULT_CONTRIBUTION_DIR) -> Mapping[str, Any]:
    payload = record.as_record() if isinstance(record, NetworkContribution) else dict(record)
    errors = validate_contribution(payload)
    if errors:
        raise ValueError("; ".join(errors))
    path = _path(root, directory, str(payload["contribution_id"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"ok": True, "contribution_id": payload["contribution_id"], "path": _rel(Path(root).resolve(), path), "record": payload}


def list_contributions(agent_id: str = "", root: str | Path = ".", directory: str | Path = DEFAULT_CONTRIBUTION_DIR) -> tuple[Mapping[str, Any], ...]:
    base = Path(root).resolve() / directory
    if not base.exists():
        return ()
    records = tuple(json.loads(path.read_text(encoding="utf-8")) for path in sorted(base.glob("*.json")))
    if agent_id:
        records = tuple(record for record in records if record.get("agent_id") == agent_id)
    return records


def export_contribution_bundle(agent_id: str, out: str | Path, root: str | Path = ".") -> Mapping[str, Any]:
    records = list_contributions(agent_id, root=root)
    bundle = {"ok": True, "agent_id": agent_id, "contributions": records, "count": len(records), "raw_payloads_excluded": True}
    path = Path(out)
    if not path.is_absolute():
        path = Path(root).resolve() / path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {**bundle, "path": _rel(Path(root).resolve(), path)}


def _path(root: str | Path, directory: str | Path, contribution_id: str) -> Path:
    safe = "".join(ch for ch in contribution_id if ch.isalnum() or ch in {"-", "_", "."}).strip(".")
    if not safe:
        raise ValueError("contribution_id is required")
    return Path(root).resolve() / directory / f"{safe}.json"


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
